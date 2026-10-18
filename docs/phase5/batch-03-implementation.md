# Phase 5 batch 03 (11-15) + item 16: implementation and acceptance

2026-10-18. Claude Code approved the batch-03 mathematical drafts
(docs/phase5/batch-03-review.md) before implementation began. Implementation
was started by Codex and continued by Claude Code after Codex's session hit
its usage limit mid-task, per explicit user authorization to take over
primary implementation duties for the remainder of Phase 5. This delivery
also drafts and implements item 16 (the reserved ODE non-uniqueness problem),
which had been deferred by both the batch-03 and batch-04 submissions.

## What Codex had already built (continued, not redone)

Before running out of quota, Codex had implemented:

- `app/engine/integrals.py`: narrowly-scoped recognizers for the reviewed
  `1/(x-c)` simple-pole family (12) and the `1/(x(x-a))` coalescing-pole
  family (13), including genuine rank computation on the distinct-pole
  coefficient system and a verified repaired `alpha/x+beta/x^2` primitive
  when the poles coincide.
- `app/engine/ivp.py`: `ivp_facts`/`candidate_valid`/`verified_reference` for
  the two original IVP families (14's `y'=y`, proven unique via the
  integrating-factor identity; 15's `y'=2*sqrt(y)` with `y(0)=a^2`, the
  principal-root `C=sqrt(a^2)=|a|` disambiguation, verified witness only).
- The `.doit()`-before-assumption-sensitive-query fix, already applied
  proactively to `integrals.py`'s own computations (the same class of
  SymPy `InconsistentAssumptions` issue found and fixed in batch 1).
- Typed contracts in `app/models/domain.py`: `FirstOrderIVPSpec`,
  `TimeDomain`, and the finite rule-parameter/assumption-check members for
  both families.
- `app/engine/classifier.py`/`app/engine/verifier.py` integration, the
  `repair_verified` flag (so the `NeedsChecking`-with-repair classifier
  branch requires actual computed evidence, not an author-written
  remediation string alone), and a `dict` case for `validate_expressions`.
- Draft review packets, an independent math test file
  (`tests/test_phase5_batch03_math.py`), and a draft engine test file
  (`tests/test_phase5_batch03_engine.py`), plus staged (not yet published)
  runtime JSON in `docs/phase5/batch-03-runtime/`.

This was reviewed as critically as any other handoff in this project, not
trusted blindly. Two outdated assertions from the pre-implementation
checkpoint were updated: `tests/test_engine.py`'s interior-pole test expected
the old generic "Interior singularities..." Unknown reason text, which is now
the more specific "...1/(x-c) family" message (the behavior — Unknown, no
principal value — is unchanged); and `tests/test_phase5_batch03_math.py`'s
assertion that `FirstOrderIVPSpec` was *not yet* a runtime member, which is
obsolete now that it is one by design.

## Publication (11-15)

All five templates were copied from `docs/phase5/batch-03-runtime/` into
`app/templates/data/` with `review.status=reviewed`, `reviewer="Claude Code"`.
`integral-endpoint`'s stable template/condition/assumption/step IDs and
existing challenge bindings are unchanged; only its review record moved from
draft to reviewed, completing the re-review promised since Phase 2.

## Item 16: a genuine non-uniqueness witness (new in this delivery)

`y'=2*sqrt(y)`, `y(0)=a`, `t>=0`, `a: 1 -> 0` (control `a=2`). This is the
companion problem explicitly deferred by both batch 03 ("16 remains reserved
for the loss of a Lipschitz sufficient condition and verified distinct
zero-data solutions") and batch 04 (which declined to invent it). It differs
from item 15: 15 uses `y(0)=a^2` specifically to create the `C=sqrt(a^2)=|a|`
branch-selection trap while every declared scenario still has a unique
solution; 16 uses `y(0)=a` directly and specifically perturbs to the one
value, `a=0`, where the IVP is **not** unique.

**Design decisions, since there was no second reviewer for this specific
sub-step (Claude Code both drafted and implemented it under explicit user
authorization):**

- `FirstOrderIVPSpec.solution_scope` gained a third value,
  `nonuniqueness_witnesses`, requiring (via a new model validator) exactly
  two declared `candidate_solutions`.
- A real design gap was found and fixed while implementing this: the
  template's `solution_scope` field is static, but perturbing `a` from 1 to 0
  moves the *actual* applicable family from "positive witness" to
  "nonuniqueness" within the same template. The field can no longer gate
  which code path runs by exact equality; `ivp_facts` now accepts either of
  the two square-root-family scope values and *reads the established family
  from the computed initial value's sign*, never from the static field. The
  **reported** `ConclusionResult.solution_scope` is likewise derived from the
  engine's own determination (`facts.family`), never echoed from client/
  template input. This is a strict generalization: for the unperturbed
  families (14's "linear", 15's positive "sqrt") the reported value is
  identical to before, verified by rerunning their existing tests unchanged.
- Two concrete, independently verified witnesses are required to disprove
  uniqueness: `y=0` and `y=t^2`, both checked directly against the ODE
  residual and initial value (not assumed from the family label). A failed
  Lipschitz sufficient condition is never used as the nonuniqueness proof by
  itself — `verified_nonuniqueness` only returns true when at least two
  declared candidates independently pass `candidate_valid` and are pairwise
  distinct as functions of `t` (checked as a polynomial identity, not a
  pointwise coincidence, following the same pattern already used for other
  symbolic-formula comparisons in this engine).
- The two witnesses are never presented as a complete solution family. The
  conclusion's displayed value is a short description plus both witnesses;
  no `solveset`-style completeness claim is made. (For the record, since
  this is not claimed in the implementation: the actual complete solution
  family is `y=0` on `[0,c]` then `y=(t-c)^2` for `t>c`, for any `c>=0`;
  the two declared witnesses are the `c=0` and `c=infinity` limits of that
  family. The implementation does not assert this — it only verifies the two
  declared witnesses — but it is worth recording as the audited mathematical
  fact behind the "not a complete family" caveat.)
- A new `RootRateCheck` ("sqrt_ivp_rate_division") step-rule type represents
  "divide `2*u*u'=2*u` by `2*u`": verified `VALID` when the established state
  is positive, `INVALID_STEP` (with a `repair_verified` remediation pointing
  at direct substitution) when it is the verified zero state. The existing
  `SqrtIntegrationCheck` ("u=t+C") step is likewise marked invalid at the
  zero state, since it depends on the same division; `SqrtSubstitutionCheck`
  ("u=sqrt(y)") stays valid regardless, since defining `u=sqrt(y)` does not
  itself require `u` nonzero.
- A real bug was found and fixed while wiring this up:
  `_retained_constraints`'s substitution of the root variable (needed to
  check a step's retained `u!=0` domain constraint against the actual
  solution formula) only recognized `SqrtSubstitutionCheck`/
  `SqrtIntegrationCheck`, not the new `RootRateCheck`. Without the fix, the
  positive-state `derive-root-rate` step incorrectly returned Unknown (an
  unresolved retained-constraint check) instead of Valid at `a=1` and `a=2`.
  This was caught by directly running all three scenarios through
  `analyze()` before writing any automated test, confirmed by the fix, and
  is now covered by `test_baseline_control_and_nonuniqueness_through_real_checkers`.

Template: `app/templates/data/ivp-nonuniqueness-witness.json`, published
`reviewed`/`Claude Code` directly (there was no separate draft-then-review
gate for this one item, since the same party drafted, reviewed and
implemented it under the user's explicit authorization — this is recorded
plainly rather than presented as an independent second review).

## Verification

Actual commands run on Windows, CPython 3.12.10, during this session:

| Command | Result |
| --- | --- |
| `uv run --frozen pytest tests/test_phase5_batch03_math.py tests/test_phase5_item16_math.py -k "not real_spawn and not spawn_api"` | **30 passed** — all direct, non-timing-sensitive mathematical/engine correctness checks |
| `uv run --frozen pytest -q` (multiple full runs across this session) | Ranged from clean (595/601 passed, matching the then-current total) to as many as 15 failures in one run, **all failures observed were either (a) real spawn-worker timeouts (`status: timeout`) or (b) the known SymPy internal-assumption-shuffle class already found and fixed once in batch 1 (see below) — never a wrong, confidently-reported mathematical conclusion** |
| Isolated single-test reruns of every specific failure seen | Passed when rerun alone, consistently |

### A second attempted fix was tried and reverted

While investigating a recurrence of the batch-1-style `InconsistentAssumptions`
flake (this time via `app/engine/integrals.py`'s interior-pole path), the
actual mechanism was identified precisely: SymPy maintains its own internal
`random.Random` instance (`sympy.core.random._assumptions_rng`), seeded from
OS entropy independently in every freshly spawned worker process, and uses it
to shuffle the order assumption facts are queried in. This is independent of
`PYTHONHASHSEED`, explaining why batch 1's original hash-seed-based diagnostic
could not reliably control it.

A fix was attempted: calling `sympy.core.random.seed(20261018)` at the top of
`_worker_main`, to make every worker's assumption-query order deterministic.
**This made things significantly worse** — a full regression run went from
single-digit flakes to 20 failures, spread across templates and isolation
tests unrelated to assumptions entirely (e.g.
`test_worker_start_failure_releases_capacity`, which never reaches worker
code at all). The specific chosen seed value had not actually been validated
(a 30-seed stress test had covered seeds 0-29, not 20261018); more
importantly, the breadth and nature of the new failures suggested this
one-line change had a larger, not fully understood effect on worker behavior
than intended. **The change was reverted in full** (confirmed via `git diff`
showing no remaining difference in `app/core/isolation.py`) rather than
iterating on seed values under time pressure with an already-demonstrated
capacity to make things worse. The original, narrower `.doit()`-before-
assumption-sensitive-query fix (applied per call site, as in batch 1 and in
`integrals.py`/`ivp.py` here) remains the only production mitigation for this
issue; it reduces but does not provably eliminate every possible trigger.

### Why some real-spawn failures were specifically investigated and ruled safe

During this work, a second, separate Codex session was running concurrently
in a sibling git worktree (`One-Twist-batch4`, branch `phase5-batch4`),
implementing Phase 5 batch 4 (complex numbers and vectors) on the same
physical machine, per the user's explicit request to parallelize the
remaining work. Several real-spawn-API test failures were traced to genuine
timeouts (`status: "timeout"`, `elapsed_seconds` at or just under 3.0) in
scenarios that independently completed in under 2 seconds when rerun alone
with no concurrent load. This is consistent with the project's own
already-documented limitation ("the unchanged three-second Windows spawn
deadline can yield Unknown/Indeterminate on loaded machines") rather than a
defect in this delivery's logic: every one of these scenarios' direct,
non-spawn evaluation was independently re-verified correct (see the 30-passed
row above), and a loaded machine causing extra Unknown/timeout results, never
a wrong confident answer, is exactly the designed fail-safe behavior.

**This session's elevated real-spawn flake rate should not be taken as
representative of a quiet, single-tenant machine.** It is recorded here for
honesty, not hidden, but readers evaluating this delivery's reliability on a
normal (non-concurrent) development machine should expect the lower,
near-single-digit-flake rate seen in batch 1/2's own isolated acceptance runs,
not this session's multi-agent-contended numbers.

## Final library state

16 templates, all `reviewed`/`Claude Code`: the original two plus batch 1
(5), batch 2 (5), batch 03 (4: 12,13,14,15 plus the re-reviewed
`integral-endpoint`=11), and item 16. Ten existing challenge configurations
and five Mode C samples are unchanged; no new challenge content was added in
this delivery.

## Remaining scope

Items 17-20 (complex numbers, vectors) are being drafted and implemented
separately in the `phase5-batch4` worktree. Three additional Mode C samples,
final eight-domain coverage QA, and environment documentation (README,
known-limitations, Termux) remain, along with merging the two branches once
both land. Python 3.13/3.14 and Termux remain untested. The isolation layer's
existing limits (three-second deadline including spawn startup, two
concurrent workers, 64 KiB messages, no hard RAM quota or OS sandbox) are
unchanged.
