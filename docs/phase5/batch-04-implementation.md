# Phase 5 batch 04 (17-20): implementation and acceptance

2026-10-18. Codex drafted and got independent math/contract approval for this
batch (`batch-04-review.md`, `batch-04-spec-design.md`) before hitting a usage
limit right before implementation started. Per explicit user authorization,
Claude Code took over as primary implementer for the remainder of this batch,
holding itself to the same independent-verification standard applied
throughout the project (hand-computed math, real regression, no guessing).

## What was implemented

Four new templates, all published `review.status=reviewed`,
`reviewer="Claude Code"`:

| # | id | Main boundary | Non-breaking control |
| - | -- | -------------- | --------------------- |
| 17 | principal-argument-product | p=-1: unwrapped sum 3*pi/2 wraps to -pi/2 | p=2 |
| 18 | real-square-to-complex-domain | widen to C: roots {-i, i}, real order theorem inapplicable | restrict to nonnegative reals |
| 19 | vector-angle-zero-norm | a=0: zero vector, angle undefined | a=2 |
| 20 | line-intersection-all-coordinates | c=1: skew (z-residual fails) | b=2 (pure re-parametrization) |

New contracts in `app/models/domain.py`: `PrincipalArgumentSpec`,
`VectorAngleSpec` (fixed 2/3-tuple `ScalarVector`), `Line3D` /
`LineIntersection3DSpec`, `LineRelation` enum and `LineRelationOutcome`
(intersection point only ever populated when `relation=intersecting`), plus
finite `RuleParameters`/`AssumptionCheck` members
(`ArgumentPairCheck`/`ArgumentAdditivityCheck`, `RealSquareNonnegativeCheck`/
`RealOrderAvailableCheck`, `ClaimEmptySolutionSetCheck`, `VectorStepCheck`/
`VectorNormsNonzeroCheck`, `LineXYCandidatesCheck`/
`VerifyLineCommonPointCheck`/`ClaimLineRelationCheck`/
`LineDirectionsNonzeroCheck`). `ConclusionResult`/`ConclusionComparison` gained
a `line_relation` status/basis whose comparison in `classifier.py` reads the
typed relation/point, never LaTeX or the t/s line parameters — the template 20
control is deliberately a pure re-parametrization, so comparing parameters
would misreport "changed".

New module `app/engine/complex_vector.py` holds the finite facts:
`principal_argument_value` (zero input -> `undefined`, not Unknown or `nan`;
non-zero verified real/finite and inside the declared `(-pi, pi]` branch
before being trusted), `argument_additivity_data` (recomputes both factors'
arguments and the actual product's argument independently, then checks
whether the *unwrapped* sum already lands in-branch — the step 2/3 checkers
and the `principal_argument_additivity` assumption all share this one
function so there is exactly one place that decides additivity),
`vector_angle_facts` (dot/norms via bounded scalar sums, zero-norm -> explicit
`None` angle, Cauchy-Schwarz range checked before `acos`), and
`line_intersection_facts` (solves **all three** coordinate residuals via
`sp.linsolve`, classifies intersecting/skew/parallel_distinct/coincident from
the solution shape plus the direction cross product).

`solve_equation` in `verifier.py` gained a narrow complex branch
(`complex_polynomial_roots`): degree-1/2 polynomials only, closed finite
rational-ish coefficients, solved via `S.Complexes`, every root re-verified by
substitution before the result is marked `complete`. `evaluate_problem`'s
earlier real/integer admissible-domain pre-check is skipped for complex
variables (that check itself raises for complex) rather than being
generalized — the complex path has no additional-constraint support in this
batch by design (`solve_equation` raises if any are present).

`app/templates/loader.py`'s `validate_expressions` recursed into `list` but
not `tuple`; since the new vector/line specs use fixed-length tuples for
coordinates, this was a real gap (a malicious tuple component would have
skipped parser validation). Fixed by adding `tuple` alongside `list`; a
regression test (`test_malicious_vector_component_is_rejected_at_load_time`)
proves a hostile `u` component is now rejected at load time, not silently
accepted.

## A real bug found and fixed during implementation

`line_intersection_facts`'s "is this a unique intersection point" check
originally only tested `isinstance(solution, sp.FiniteSet) and len(solution)
== 1`. For **coincident** lines (same line, different parametrization),
`sp.linsolve` on an underdetermined 2-equation-but-1-independent system
returns a length-1 `FiniteSet` whose tuple entries are themselves symbolic in
the free parameter — not a concrete point. The original code mistook this for
a genuine unique solution, then hit its own parallel-direction guard and
raised `UnsupportedMath` instead of correctly classifying the case as
`coincident`. Fixed by checking `t_value.free_symbols`/`s_value.free_symbols`
first: a free-symbol "solution" together with parallel directions is
`coincident`; without parallel directions it would be a genuine
inconsistency (raises). Caught by
`test_20_parallel_distinct_and_coincident_classification`, which failed
before the fix and passes after.

## Verification

All commands run from `C:\Users\scjor\OneDrive\Documents\One-Twist-batch4`
(a separate git worktree on branch `phase5-batch4`) on Windows, CPython
3.12.10.

| Command | Result |
| --- | --- |
| `uv run --frozen pytest -q` (x3 consecutive) | **585 passed** each time, 1 existing Starlette/HTTPX warning, ~90s each |
| `uv run --frozen pytest tests/test_phase5_batch04_engine.py -v` | **17 passed** |
| `npm.cmd test` (frontend) | **49 passed** (unchanged — no frontend code was modified) |
| `npm.cmd run build` | Passed; 558.38 kB / 169.66 kB gzip, pre-existing chunk-size advisory |

The three consecutive full-suite runs were specifically to stress-test
against the randomized-SymPy-assumption-order flake class that this project
hit twice before (batch 01's `InconsistentAssumptions` bug, root-caused to
`simplify()` being handed an unevaluated syntax tree before `.doit()`). All
new numeric code paths in `complex_vector.py` call `context.expr(...)` (which
already does `.doit()` before `simplify()`) rather than operating on raw
unevaluated trees directly, so this class of bug should not recur here; the
three clean repeated runs are supporting evidence, not proof.

`test_phase5_batch04_engine.py` includes real spawned-worker API round trips
(`client.post("/api/analyze", ...)` through the actual isolation executor)
for the main boundary case of all four templates, confirming
`execution.status == "success"` and the exact expected report fields —
not just in-process `analyze()` calls. It also covers: `Arg(0)` is
`undefined`; `arg(-1) == pi` (not `-pi`); an ordering predicate on a complex
`DomainChoice` is rejected by the existing `no_complex_ordering` validator; a
non-polynomial complex equation returns Unknown rather than a guess; a
vector-dimension mismatch is rejected at the model level; a zero line
direction returns Unknown; the template 20 control is confirmed `changed:
False` despite `b` changing (the re-parametrization case); a case where only
the x/y components match but z does not is confirmed `Invalid Step`, not
misreported as intersecting; and adversarial component sources
(`__import__`, attribute-escape attempts) are rejected both at the bounded
parser level and at template-load time.

Five pre-existing tests in other batches' files hardcoded the total template
count/ID set as 11; these were updated to the new count of 15 (10 pre-batch
+ the existing `integral-endpoint` snapshot + these 4) — this is an expected
consequence of adding templates, not a regression, and no test's underlying
assertion about *content* was weakened.

## Simplification versus the original workflow

Earlier batches used a private staging directory and a
`scripts/build_phaseN_batchNN.py --publish` step to convert reviewed JSON
packets into runtime templates only after acceptance. Given the compressed
circumstances (continuing Codex's already-approved draft under a context
budget), this batch's four Template JSON files were written directly into
`app/templates/data/` with `review.status: "draft"` and only flipped to
`"reviewed"` after the full verification above completed cleanly. The
net safety property (nothing is publicly reviewed-and-trusted until verified)
is the same; the intermediate staging artifact was skipped. No build script
for batch 04 was added as a result — this is a known, intentional process
deviation from the batch 01-03 convention, not an oversight.

## Remaining scope (unchanged from the approved design)

Complex solving is restricted to closed degree-1/2 polynomials; no general
complex CAS. Vector/line specs are fixed 2D/3D tuples of scalar expressions,
never matrix/array input. The restricted arithmetic parser gained no new
callables (`arg`/`acos`/`diff` construction all happens in trusted checker
code, never in user-reachable grammar). `Arg`'s branch is fixed to
`(-pi, pi]`; complex logarithm branches are out of scope. Ten more templates
(including `integral-endpoint`'s own formal re-review, scheduled for batch
11-15), three extra Mode C samples, final 8-domain coverage QA, and the
Termux/Python-3.13+/3.14 verification checklist remain open Phase 5 work.
Python 3.13/3.14 and Termux were not tested in this delivery.
