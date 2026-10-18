# Phase 2.1 isolation acceptance handoff

Scope: isolation infrastructure only. Phase 2.2–2.7 awaits reviewer confirmation.
No mathematical engine, template computation specs or new public API operations
were implemented. Existing mathematical/challenge POST routes remain HTTP 501.

## Implementation

- `app/core/isolation.py`: application-owned `ComputationExecutor`, explicit
  spawn context, one disposable process per job, single-use one-way Pipe and
  JSON bytes, with a 64 KiB limit on each request/result.
- A separate receiver thread drains results while the supervisor owns the
  monotonic deadline. The default is three seconds including startup; cleanup
  has separate bounded grace periods.
- Cleanup uses terminate, join (0.5 s), kill if still alive, join (0.5 s), then
  confirms receiver exit (0.5 s), closes resources and releases capacity.
  Cleanup uncertainty stops new admission and retains the occupied slot.
- At most two admitted jobs per application executor, no waiting queue.
  Results distinguish success, timeout, worker failure, result limit and shutdown
  cancellation, with PID/exit-code/timing diagnostics. They make no mathematical
  validity claims.
- `app/main.py`: executor lifecycle ownership, threaded shutdown and a shared
  HTTP 503 mapping for executor unavailability. The synchronous computation
  route used in HTTP tests is test-only; it is absent from the production app.
- Only an internal `ping` operation exists. Fault targets live in
  `tests/isolation_workers.py`; clients cannot select them or supply a callable.

## Windows startup issue found and fixed

An early-startup termination regression exposed a real CPython Windows issue:
its default Pipe reducer places a temporary writer handle in the parent for the
child to steal during unpickling. If the child is killed first, the stranded
writer prevents EOF and the receiver stays blocked.

The small `_WindowsSpawnWriter` adapter duplicates the writer directly into
the spawned child using the launcher's handle-transfer facility. Child death
then closes that handle even before unpickling. Parent and child cleanup were
verified without weakening the receiver-exit assertion. This is documented in
[ADR 001](adr/001-symbolic-computation-isolation.md).

## Actual validation

Environment: Windows, CPython 3.12.10.

Executed:

```powershell
uv run --frozen pytest -q -o junit_family=xunit1 --junitxml=.pytest_cache/phase2-1-results.xml
```

Result: **146 passed, 1 warning in 11.54 s**. The warning is the same pre-existing
Starlette HTTPX TestClient deprecation. The report contains **29 passing isolation
cases**; all other Phase 1 regression tests also passed.

| Acceptance case | Observed result |
| --- | --- |
| Normal execution | Different PID, spawn method, validated JSON result, exit code 0 |
| Executing infinite loop | Ready marker proves actual execution; timed out, process/reader reaped |
| Result sent followed by infinite loop | Still times out; a premature result does not bypass process cleanup |
| Exception / abrupt exit / no result | Explicit worker_exception / worker_exit / missing_result |
| Exact 64 KiB frame | Received successfully without join-before-read deadlock |
| Oversized generated/raw result | Producer and receiver limits both enforced |
| Malformed/non-finite result | Protocol failure, never success |
| Timeout recovery | Occupied slot released; next normal request succeeds |
| Third task | Immediate capacity rejection; no third worker or queue |
| HTTP rejection and concurrent GET | Test-only synchronous route returns 503; template GET returns 200 with two templates while both workers run |
| Application lifespan shutdown | Active loop cancelled; process and result thread reclaimed; new work refused |
| Spawn failure | Failure reported and capacity recovered |
| Startup deadline | Artificial startup delay counts against the deadline; early termination reclaims resources |
| Repeated early Windows termination | Eight terminations; process handle count **227 before / 227 after**; no remaining workers/result threads |
| Kill escalation | Controlled process double verifies terminate → bounded join → kill → bounded join |
| Cleanup failure policy | Stops admission and does not claim the slot is free |

JUnit measurements report approximately **3.0 s** for each real infinite-loop
timeout. Core rejection passed a **0.25 s** threshold; HTTP rejection and GET
each passed a **1 s** threshold. Their recorded elapsed values were 0.0 s at the
available clock resolution, so no sub-millisecond performance claim is made.

For an isolation-only rerun:

```powershell
uv run --frozen pytest tests/test_isolation.py -q
```

## Review follow-up: startup exception coverage

Moved Pipe creation into the startup exception handler and added ImportError
and AttributeError to the handled startup failures. Regression cases inject
Pipe resource exhaustion and both private-interface errors during real Windows
spawn serialization. Each returns failed / worker_start_failed, releases
capacity and permits a subsequent successful computation.

After this fix, `uv run --frozen pytest tests/test_isolation.py -q` completed
with **32 passed, 1 warning in 12.11 s**. The warning is the same TestClient
deprecation. The full-suite result above predates this follow-up; the full suite
was not rerun for this small fix. Phase 2.2–2.7 remains pending confirmation.

## Limits and review points

- `_WindowsSpawnWriter` uses CPython's internal spawn handle interface. Tested
  on Windows CPython 3.12.10; Python 3.13/3.14 and Termux are not yet validated.
- Windows kill is not stronger than terminate. The escalation ordering is
  tested with a double; real Windows loop workers exit on terminate.
- No hard RAM quota or OS security sandbox is claimed. The result channel
  accepts JSON only; CPython spawn itself still serializes trusted application
  objects internally.
- A synchronous OS-level stall inside `Process.start()` cannot itself be
  preempted by this supervisor. Startup time is counted and the remaining
  deadline is enforced immediately after the call returns. Cleanup grace is
  separate from the compute deadline.
- API 501 behavior is unchanged. Mapping execution failures to mathematical
  Unknown, adding computational specs and registering actual mathematics are
  explicitly deferred until the reviewer authorizes Phase 2.2–2.7.
- Frontend files and dependencies were unchanged; frontend checks were not
  repeated for this backend-only isolation delivery.
