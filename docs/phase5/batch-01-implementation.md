# Phase 5 batch 01 implementation and acceptance

2026-10-18. Claude Code approved the typed-contract design and the detailed
01-05 mathematics before implementation. This delivery implements those five
templates, publishes their review records, and submits the next five drafts.
It is not completion of the twenty-template Phase 5 library.

## Published content and runtime changes

| No. | Template | Main boundary | Non-breaking controls |
| --- | --- | --- | --- |
| 01 | linear-degeneration | a=0 makes division invalid; original equation has no solution | a=2,-1 |
| 02 | cancelled-factor-domain | Widen R minus {2} to R: cancellation loses root 2 | Restrict x<2 |
| 03 | squared-candidates-sign | c=6 gives squared candidates {4,9}, original solution {9} | c=-1/4: repeated valid root 1/4 |
| 04 | inverse-square-domain | Widen nonnegative x to R: principal inverse loses -1 | Restrict x>=1/2 |
| 05 | real-log-product | t=-1: log(t*t)=0 while 2log(t) has no real value | t=2: valid rewrite, changed value |

The default library now has six entries. These five are reviewed, reviewer
Claude Code; integral-endpoint remains draft until its scheduled batch 11-15
formal re-review. No new challenge configurations or AI samples are published.
Existing challenge rule IDs on linear-degeneration are preserved.

`app/models/domain.py` adds DomainSpec, a condition-owned DomainConditionBinding,
named DomainChoice values, ScalarExpressionSpec, explicit domain/candidate
assumption scopes, and four discriminated step-rule parameter members.
Domain perturbations accept a declared choice_id with new_value=null. Other
changes retain their existing value contract. Malformed combinations are 422.

Restrictions in 02/04 were **moved** from fixed problem.domain_constraints to
the owning condition, not copied. The model rejects duplicate ownership of the
same predicate. The constructor updates that condition and the variable number
system together. Independent retained step constraints survive the change;
the baseline template is never mutated.

`context.py` builds the effective domain from immutable restrictions and current
condition-owned restrictions. Scalar definedness traverses every unevaluated
intermediate before simplification, including parameter construction. Tests
include cancelling complex logarithms, multiplying imaginary square roots and
zero times an undefined reciprocal. None may become a valid real calculation
through simplification. The 0**0 convention explicitly remains Unknown.

`assumptions.py` checks domain inclusion separately from a predicate on the
complete candidate set of a specified equation. `verifier.py` computes that
candidate set and compares accepted roots with an independently solved original
equation. Added step checks are scalar identity, scalar evaluation, candidate
solving and candidate acceptance. A violated premise alone still cannot prove
an invalid step. Partial/conditional roots and unsupported definedness stay
unresolved. The parser grammar and isolation limits have not expanded.

The existing analysis/perturbation endpoints use these rules through actual
spawn workers. Expected-answer text and expected_failure_mechanisms remain
outside runtime evidence. Tests poison them and obtain identical analyses.
No golden scenario table is imported by production code. Scalar comparison
uses exact computed values; log(4) and 2log(2) are equivalent presentations.

The frontend adds a declared-domain selector and KaTeX domain summaries to
problem/condition comparisons. Explorer and Mode B construct canonical domain
payloads; Mode B's new-domain path has a synthetic backend acceptance binding,
without adding a public challenge. Existing session/race/error handling and
independent step/method/conclusion reports are reused.

`scripts/build_phase5_batch01.py` retains the review-to-runtime conversion for
inspection: its default output is private staging; --publish writes approved
content/review records. Staging is not loaded by the normal app. The publication
test compares staged and published mathematics excluding review metadata.
The actual first publication followed successful real-checker/API tests and a
396-test full backend run; final acceptance below includes subsequent additions.

## Verification

All results below are actual Windows runs with CPython 3.12.10. Backend full
regression and live frontend computations were run sequentially. No production
timeout or concurrency setting was relaxed for acceptance.

| Command | Actual result |
| --- | --- |
| uv run --frozen pytest -q | 426 passed, 1 existing Starlette/HTTPX warning; 57.41s |
| uv run --frozen pytest tests/test_phase5_batch02_math.py -q | 20 passed; 0.26s |
| npm.cmd test | 46 passed; 2.86s |
| npm.cmd run build (includes typecheck) | Passed; JS 558.31 kB / 169.63 kB gzip; existing chunk-size advisory |
| npm.cmd run test:integration | 7 passed; 12.23s; actual Vite proxy/FastAPI/spawn path, including domain widening and unchanged log conclusion |
| npm.cmd run test:browser | 14 passed; 41.6s; installed Edge, desktop 1440x1000 and mobile 390x844 |

The in-app browser could not connect (missing sandboxPolicy before execution).
The actual browser acceptance used the installed Edge fallback. All four new
domain/log desktop/mobile screenshots were visually inspected and are retained
under frontend/test-results (ignored by Git). The development services started
for acceptance have been stopped; neither port remains listening. These
viewport checks do not constitute physical mobile-device or Termux testing.

Inspecting all six exported API fixtures found a largest analysis JSON of
17,011 UTF-8 bytes (with ordinary JSON spacing, a conservative overestimate of
the compact worker message). The largest baseline worker request is 6,619
bytes. Both are below the unchanged 65,536-byte message cap; real-worker tests
also exercised every first-batch scenario through that cap.

The 61 new batch-01 runtime cases include the 16 approved scenarios both
directly and through real isolated HTTP, widened/restricted domain ownership,
candidate-scope contracts, raw-tree real definedness, non-tautological premise
failure, metadata poisoning, reviewed publication, synthetic Mode B domain
grading, and eight fixed-hash fresh-worker comparison regressions. The existing
32 first-batch independent mathematical tests remain in the full suite.

Publication exposed an old isolation GET test's hardcoded two-template count.
The endpoint correctly returned six; the test now compares against the loaded
inventory while retaining its actual capacity/GET responsiveness checks. The
first postpublication full run had 425 passes and that one failure; the final
run above passed all 426.

One earlier scoped run returned only Valid for the radical c=-1/4 conclusion,
where Valid + Changed Conclusion was expected. Execution reported success
(about 0.813s), so this is **not established to be a timeout/resource-contention
failure**. The original assertion lacked the complete comparison report; its
cause remains unestablished. Eight subsequent fresh-worker checks and a separate
32-fixed-hash diagnostic all established changed=true, as did both subsequent
full runs. Full-report diagnostics and eight fixed-hash regression cases remain.
No code forces changed=true or substitutes an authored answer to hide this
observation. The temporary diagnostic script was removed.

Update after independent review: Claude Code reproduced this failure in the
full suite. It has now been traced to simplifying a deliberately unevaluated
`x + (-1)*0`, where SymPy's randomized assumption queries can raise
InconsistentAssumptions. The baseline became Unknown, while the perturbed
solution was correct. This was not a set-comparison defect or a timeout.
The computation copy is now evaluated before simplification; raw syntax and
its domain exclusions remain intact. Deterministic adverse-order regressions
reproduce failure before the fix and exercise actual spawn/API execution after
it. See [root-cause and repair evidence](batch-01-radical-fix.md). The preceding
paragraphs record the original delivery's incomplete investigation, not a
remaining accepted limitation.

## Next review and limits

[Batch 02 review packet](batch-02-review.md) contains five draft JSON packets,
fifteen scenarios and explicit mathematics for 06-10: sine branches, cosine
quadrant sign, a cusp derivative, degenerate second-derivative classification
and L'Hopital's required form. Independent tests establish the actual roots,
one-sided difference quotients, neighborhood sign witnesses and limits. All
five remain draft/reviewer=null and outside the public loader. Their future
specs/checkers have not been implemented; explicit mathematical approval is
the next gate.

The current solver is finite, scoped and real-domain; general complex solving,
arbitrary proof rules, derivative/classification computation specs and the
remaining Phase 5 families are not implemented. The remaining fifteen reviewed
templates, three extra C samples, final coverage QA and complete Termux
verification checklist are still scheduled work. Termux and Python 3.13/3.14
have not been tested. The unchanged three-second deadline includes Windows
spawn startup; a loaded host can still return Unknown/Indeterminate. There is
no hard RAM quota or OS security sandbox.
