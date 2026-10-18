# ADR 001: Symbolic computation in disposable spawned processes

Status: Phase 2.1 independently accepted; Phase 2 engine integration implemented.

## Context

One-Twist runs on Windows and should be practical on Termux. SymPy operations
can take unpredictable time even for syntactically valid expressions. A timeout
on an HTTP request or a Future does not stop an already running calculation.
Input syntax validation and calculation containment are separate requirements.

## Decision

Use Python `multiprocessing.get_context("spawn")` with one disposable child per
calculation. The parent is responsible for the deadline and worker cleanup.
No Redis, external task queue, persistent worker framework or microservice is
needed for the MVP.

1. The API accepts a template ID, an allowed rule and a single condition change.
   It reloads authoritative template facts and validates the change server-side.
2. Send a small serializable request with an allowlisted operation identifier,
   bounded mathematical syntax and explicit domain/parameter facts. Do not send
   client-selected Python callables or import paths. The child validates input
   again before constructing mathematical objects.
3. A module-level child entry point runs the approved operation and emits a
   bounded JSON result through a one-way pipe. Input and output are limited to
   64 KiB each. An independent receiver thread drains the result while the
   calling supervisor enforces the deadline; it never blocks on receiving a
   frame or waits for process exit before draining the pipe. Mathematical
   operations construct SymPy objects inside this boundary.
4. A monotonic deadline includes process startup and calculation. On expiry,
   terminate the child, join with a short cleanup deadline, then kill and join
   if still alive. Close pipe endpoints on success, timeout and exceptions.
   Never fall back to computing inside the API process. Each join gets a 0.5 s
   grace period; the result thread gets a further 0.5 s to exit. Only release
   capacity after both worker and receiver have been reclaimed. A cleanup
   failure makes the executor unavailable and retains the occupied slot.
5. Start with at most two active calculations per API process and a default
   three-second deadline, then adjust using the reviewed content corpus.
   Reject excess capacity explicitly rather than growing an unbounded queue.
   The application maps executor unavailability to HTTP 503. Calculation routes
   are synchronous FastAPI handlers, so waiting happens in its thread pool.
   Lifespan shutdown also runs executor cleanup in a thread and stops admission
   before signalling active supervisors to cancel and reap their workers.
6. A computation timeout produces Unknown for the checks it prevented, with
   a specific reason. Worker failure and incomplete symbolic results also
   retain explicit reasons; none is evidence of a false mathematical claim.
   Invalid input remains an API validation error, rather than Unknown.

The process boundary is for calculation containment. It does not authorize
execution of user code and is not an operating-system security sandbox.
The Phase 1 parser already avoids eval/exec and limits input size and structure.
Those limits do not bound the work of arbitrary subsequent SymPy operations.

## Platform consequences

- Use `spawn` explicitly on all platforms and protect command-line entry points
  with `if __name__ == "__main__"`. Do not rely on POSIX fork, signals or
  `resource.setrlimit` for required Windows behavior.
- `terminate()` cannot be assumed to run child cleanup handlers. Workers must
  not own persistent writes, locks shared with the API, or descendant processes.
- A wall-clock deadline is not a hard RAM quota. Strict memory enforcement is
  not claimed. Expression budgets and low concurrency are the first controls;
  Windows Job Objects or platform-specific limits need separate evaluation if
  required by observed content workloads.
- Termux compatibility remains best effort until tested on a real device.

## Windows startup-time Pipe ownership

An actual early-startup termination test exposed a CPython Windows edge case:
the default `PipeConnection` reducer uses a parent-owned `DupHandle`, which the
child later steals during unpickling. Killing the child before that point leaves
the writer handle in the parent, so closing the original writer is insufficient
to produce EOF in the receiver.

`_WindowsSpawnWriter` instead uses the active spawn launcher's
`duplicate_for_child()` so that the temporary handle belongs to the child from
the outset. Its fixed rebuild function creates the child's write-only
`PipeConnection`. Killing the child then releases its writer even if it has not
unpickled the arguments. The parent closes its original writer after starting
the process. POSIX keeps the standard connection reduction path.

This small adapter depends on CPython's internal
`multiprocessing.context.get_spawning_popen` interface. CPython 3.12.10 on
Windows is tested. Other supported Python versions require platform validation.
The regression tests check early termination, no remaining result threads and
Windows handle counts across repeated early terminations. A Windows `kill()`
call uses the same mechanism as `terminate()`; it is not a stronger OS primitive.

Only the worker result channel uses JSON bytes rather than `Connection.recv()`
unpickling. Standard spawn still uses CPython's controlled serialization of the
server-owned target and arguments; no client-supplied pickle is accepted.

## Current boundary and acceptance

`app/core/isolation.py` now defines `ComputationExecutor.run()` and `close()`.
It admits internal `ping` and finite template `analyze` operations. There are no
production fault operations. POST `/api/analyze` and `/api/perturbations` use
the same service boundary. The parent validates and constructs a canonical
single change, and the child reconstructs and verifies it again. Author-supplied
expected-failure metadata is removed before dispatch. Phase 4 A/B grading reuses
this same boundary and executor capacity. C uses a reviewed fixed-sample rubric
without starting a worker; it makes no live verification claim.

Results distinguish success, timeout, worker failure, result-size limits and
shutdown cancellation. Failure messages exclude internal tracebacks; full
worker exceptions go to server logs. The service maps unsuccessful executions to
Unknown for every prevented dimension; it never falls back to parent-process
mathematics. Normal admission/cleanup unavailability keeps its HTTP 503 mapping.

Tests use real spawn processes for normal success, an executing infinite loop,
exceptions, abrupt exit, missing results, exact/oversized frames, startup
deadlines, recovery after timeout, capacity rejection and application shutdown.
A test-only synchronous FastAPI route verifies HTTP 503 and responsive template
GETs while two workers run. The kill escalation sequence is separately checked
with a controlled process double, because Windows termination already stops
the real test workers. Phase 2 API tests additionally run real isolated equation
and integral analyses and verify that failed executions erase any stale verdict.

The deadline includes startup but cannot preempt an OS-level stall inside the
synchronous `Process.start()` call. Under normal OS scheduling the supervisor
acts on the remaining deadline immediately after startup. Cleanup has its own
bounded grace periods; the compute deadline is not an exact HTTP response SLA.

References:

- [Python multiprocessing](https://docs.python.org/3/library/multiprocessing.html)
- [Python Future.cancel](https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.Future.cancel)
- [SymPy parsing warning](https://docs.sympy.org/latest/modules/parsing.html)
