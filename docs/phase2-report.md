# Phase 2 mathematical engine: implementation handoff

Status: implemented; independent review pending. Phase 2.1 isolation was already
independently accepted. This delivery implements 2.2–2.7 on the two existing
templates, with no frontend changes or additional question-bank content.

## Implemented scope

1. **Computational contracts** (`app/models/domain.py`, `analysis.py`).
   Equation/integral specs, typed finite step-rule parameters, stable
   condition-to-parameter bindings, independent assumption results, explicit
   conclusion states and solution-set completeness. Template validation checks
   the new variable/parameter/evidence references. Existing display-only math
   remains possible; missing computational sources produce Unknown.
2. **Single-condition construction** (`app/engine/perturbation.py`).
   Deep-copy authoritative template facts, verify rule/condition/type/value,
   replace exactly one declared condition and parameter, retain domain
   constraints and reset unassessed problem status. Values use exact declared
   source strings and canonical server LaTeX. Assumption removal, when declared,
   remains distinct from asserting a predicate false.
3. **Assumptions and symbolic checks** (`context.py`, `assumptions.py`,
   `verifier.py`). Ordinary function registries cover the four kinds used by the
   two templates: nonzero, parameter range, interval continuity and logarithm
   domain. Real domains and syntactic denominators survive simplification.
   Equation checks compare complete solution sets according to transformation
   direction; partial/conditional results remain unresolved. Integral checks
   verify affine maps, Jacobians, transformed endpoints and primitives by
   differentiation. Independent endpoint limits establish finite values or
   divergence; divergent contributions are never cancelled as a principal value.
4. **Classification and explanations** (`classifier.py`, `explain.py`).
   Step, method and conclusion dimensions remain independent. Failed premises
   contribute evidence rather than automatic invalidity. Missing facts mean
   Needs Checking; unsupported mathematics means Unknown. The method can have a
   repair even when its original steps fail. A later invalid step is not called
   the first when an earlier step is unresolved. Fragments require matching
   `(rule_id, outcome)` combinations; otherwise explanations use computed facts.
   The engine never generates Inconvenient from runtime or computational cost.
5. **Isolated API integration** (`service.py`, `app/core/isolation.py`,
   `app/api/routes.py`). Both calculation POST routes share canonical
   construction and the same isolated `analyze` operation. All symbolic
   verification occurs in a spawned child. Expected-failure metadata is removed
   before dispatch; authored verdicts and original numerical answers are not
   used to determine the new result. The original problem is independently
   recalculated for comparison. Steps display recomputed formulas/values and
   current parameter assignments instead of retaining stale baseline answers.
6. **Regression and documentation**. README documents requests, response
   semantics, error behavior and limits. ADR 001 now reflects the accepted
   executor and implemented engine integration. The two templates remain draft
   until the agreed Phase 5 content-review pass.

## Mathematical acceptance matrix

| Case | Independently computed outcome | Step/method behavior | Comparison |
| --- | --- | --- | --- |
| `a=1` | Complete solution set `{1}` | Valid | Unchanged |
| `a=2` | Complete solution set `{1/2}` | Valid | Changed |
| `a=-1` | Complete solution set `{-1}` | Valid | Changed |
| `a=0` | Empty solution set; NoSolution | Zero divisor makes division invalid; return to the original equation | Changed |
| `b=1/2` | `log(2)` | Valid | Unchanged |
| `b=3/4` | `log(4)` | Valid | Changed |
| `b=1` | Positive divergence | Proper-integral steps invalid; method Needs Checking with one-sided-limit repair | Changed |

Conclusion Valid means the new outcome has been independently established; it
does not mean the original numeric answer still holds. Thus Valid and Changed
Conclusion coexist for a changed, established result. NoSolution and Divergent
are outcomes distinct from Undefined or Unknown.

Additional mathematical regression fixtures cover:

- Illegal cancellation that restores excluded zero; valid cancellation when
  the original restriction is retained.
- Division that loses a root, including an attempted new nonzero restriction
  that cannot retroactively remove a root from the input.
- Squaring as an invalid equivalence versus a valid one-way implication that
  still needs reverse/candidate checking.
- Actual SymPy conditional and partial solution sets, retaining known roots
  without claiming completeness or an unchanged conclusion.
- Missing/unsupported premises, unsupported rules, an earlier unresolved step
  before a known later failure, and failed premises with independently valid
  steps.
- Undefined original expressions, contradictory conditions, unbound numerical
  evaluations and retained restrictions on computed values.
- Incorrect substitution versus a repairable singular endpoint; interior poles
  remain Unknown instead of silently returning a principal value.
- Poisoning expected-failure prose leaves mathematical reports unchanged;
  finite cases do not accidentally receive singular-endpoint/zero-divisor text.

These are in-memory regression fixtures, not additional bundled templates.

## API behavior

- `GET /api/templates` and `GET /api/templates/{id}` retain public-only DTOs,
  omitting solution steps, conclusions, verification rules and answer metadata.
- `POST /api/analyze`: `{template_id, perturbation?}`.
- `POST /api/perturbations`: the declared `Perturbation` object. This performs
  reconstruction **and** analysis through the same path as `/analyze`.
- Responses include reconstructed facts, replayed steps, report, explanations
  and execution metadata. Server-owned facts are always recomputed.
- Invalid body/undeclared or mismatched change: 422. Unknown template: 404.
  Capacity/shutdown/cleanup unavailability: 503, without queuing.
- Timeout, worker startup/execution failure or oversized result: HTTP 200 with
  explicit Unknown dimensions and reason; no stale valid step or answer.
- `POST /api/challenges/check` deliberately remains 501 for Phase 4. No grading
  rules, reviewed Mode C sample corpus or challenge workflow was added here.

## Actual verification

Environment: Windows, CPython 3.12.10, locked dependencies unchanged.

```powershell
uv run --frozen pytest -q
```

Result: **202 passed, 1 warning in 21.32 s**. The single warning is the existing
Starlette HTTPX TestClient deprecation.

- 29 mathematical engine cases.
- 14 computational-contract and perturbation cases.
- 12 analysis API cases, including real spawn workers for every acceptance
  matrix value, shared endpoint equivalence, timeout/startup failure recovery,
  capacity rejection and responsive GETs.
- All 32 previously accepted isolation regression cases and the retained
  Phase 1 model/loader/parser/content/public-API cases pass in the same run.

API tests verify that computation PIDs differ from the server and successive
requests use different child processes. Unit mathematics cases call the same
finite checker code directly for precise failure attribution; the API tests
verify the production isolation boundary separately. Real infinite-loop,
abrupt-exit and Windows handle-leak cases remain in the isolation suite.

Frontend files/dependencies were unchanged, so frontend tests and builds were
not repeated for this backend-only delivery.

## Limits and review points

Review follow-up: the repairable-method branch now changes only the method
labels to Needs Checking. It preserves the checker-provided remediation,
evidence and affected references already aggregated by `merge`, rather than
replacing them with integral-specific text. After this fix, a full rerun of
`uv run --frozen pytest -q` returned **202 passed, 1 warning in 21.21 s**,
including the existing `one-sided` remediation assertion.

- This is a finite template rule set, not a proof assistant or general solver.
  Only the two existing templates and declared values are supported content.
  Authored display/spec correspondence and relevance of individual checks still
  require the Phase 5 content review; LaTeX and prose are never parsed as proofs.
- Complex equation domains, general case-split branch coverage, nonlinear
  substitutions, zero-length integral conventions and interior singularities
  are unsupported. They do not acquire guessed validity or finite results.
- A complete result means the supported solver/domain checks returned no
  unresolved conditions; numerical sampling is not a completeness proof.
- A method repair does not make the original invalid steps valid. The endpoint
  repair is supported by verified affine substitution and independent limits.
- The isolation limits remain: three-second default compute deadline including
  startup, two concurrent workers, 64 KiB messages, separate cleanup grace,
  no hard RAM quota or OS sandbox. Windows handle transfer uses a CPython
  private interface validated on 3.12.10; 3.13/3.14 and Termux remain unverified.
- Frontend interaction remains Phase 3. Challenge grading and reviewed Mode C
  samples remain Phase 4; full question-bank expansion and final review remain
  Phase 5.

References checked against the pinned SymPy version:
[solveset and ConditionSet](https://docs.sympy.org/latest/modules/solvers/solveset.html),
[calculus and continuous domains](https://docs.sympy.org/latest/modules/calculus/index.html).
