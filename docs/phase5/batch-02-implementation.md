# Phase 5 batch 02 (06-10): implementation and acceptance

2026-10-18. Claude Code independently approved all five detailed mathematical
packets. Implementation resumed only after independent acceptance of the
batch-01 raw-arithmetic root-cause repair. That repair, raw source structure,
parser grammar and isolation limits remain intact.

## Content and computed outcomes

| No. | Actual computation | Main changed case | Non-breaking control |
| --- | --- | --- | --- |
| 06 | sin(x)=c on [0,b) | c=1/2: {pi/6,5pi/6}; principal inverse omits 5pi/6 | b=pi with c=1: {pi/2}, unchanged |
| 07 | cos(theta) | 2pi/3: -1/2, positive-root rewrite gives +1/2 | pi/6: sqrt(3)/2, valid method and changed answer |
| 08 | derivative of sqrt(x*x+t*t) at 0 | t=0: original difference-quotient limits -1 and +1, derivative does not exist | t=2: derivative 0, unchanged |
| 09 | stationary point of x^3+a*x^2 at 0 | a=0: stationary_non_extremum; original minimum claim false | a=2: local_minimum, unchanged |
| 10 | limit x/(k*x+t) at 0 | t=1,k=1: original limit 0, derivative ratio 1; not 0/0 | t=0,k=2: valid 0/0 rule, limit 1/2 |

Baseline and both changes for each template give fifteen approved scenarios.
Each changes only one declared condition. All five are published reviewed /
reviewer=Claude Code after real isolated API acceptance. The library now has
eleven templates: ten reviewed and integral-endpoint still draft, awaiting the
scheduled batch 11-15 formal re-review. No challenge configurations or AI
derivation samples were added in this delivery.

## Contracts and boundaries

`app/models/domain.py` adds DerivativeAtPointSpec, StationaryPointSpec and
LimitSpec; finite discriminated rule parameters for principal-sine coverage,
point derivatives, stationary derivative values/classification and the reviewed
L'Hopital checks; and explicit scoped assumptions for principal-root coverage,
point-formula evaluation and zero-over-zero form. Reference validation covers
the new computation/rule variables. Extra orders, arbitrary operations and
unsupported theorem-form names are rejected by the schema. The input grammar
still rejects asin/diff/limit calls: their trusted constructions occur only in
finite checkers inside workers.

ConclusionResult gains only the currently needed classification status and
typed classification payload. It cannot use a boolean/numeric value or omit
the typed payload; nonclassification results cannot carry one. Comparison
uses the typed classifications, independently of LaTeX. The result's value
field remains a display representation. A known missing point derivative is
an undefined requested quantity while the actual function/problem remains
WellFormed; it is not Unknown.

`app/engine/calculus.py` supplies shared finite mathematical facts:

- Point derivatives recognize the actual sqrt(x*x+q) family at zero, require
  a known nonnegative closed q and full real expression/problem domains, then
  compute both original difference-quotient limits. A family label or a
  punctured derivative expression is not used as the existence proof.
- Stationary classification recognizes actual closed real quadratic/cubic
  polynomials on R. Strict second-derivative signs establish extrema. If that
  derivative is zero in a cubic, opposite increments at p+h and p-h supply an
  independent proof of a non-extremum. Inconclusiveness alone is not that proof.
- Finite-point rational limits require the actual domain to contain the
  requested punctured sides. An undefined expression at the approach point
  does not invalidate its limit. Each side is computed separately.
- L'Hopital's reviewed rule is restricted to actual affine components whose
  quotient matches the problem. It checks the actual two-sided point, 0/0
  form, differentiability and nonzero denominator derivative on a punctured
  neighborhood. It separately computes the original limit and derivative ratio.

`verifier.py` integrates these facts into per-step evidence. The sine checker
verifies the actual equation is sin(x)=a closed real constant on a finite
interval, computes its complete roots, and compares with the chosen principal
root. Its evaluation step stays locally valid when another branch is omitted.
The derivative identity is verified on the explicitly retained full nonzero
real domain; it cannot silently claim the point itself. Its substitution step
checks the point domain and independent difference quotient. Stationary-value
calculations stay valid when the final minimum claim fails. Quotient-component
derivatives and evaluating the ratio remain valid even when replacing the
original limit is false.

If the L'Hopital premise is absent but both limits happen to agree, the rule
returns Needs Checking with an applicable-law repair, not Invalid Step. The
main reviewed counterexample is Invalid because actual limits differ. Scalar
identity mismatch now supplies a generic value/sign/branch repair; it does not
hardcode a cosine explanation into a general checker. Remediation still flows
from checkers through the existing merge/classifier.

`scripts/build_phase5_batch02.py` retains the reviewed-to-runtime conversion.
Default output is private staging; --publish records the actual approval after
acceptance. Expected scenarios/reference outcomes supply authoring display and
test metadata only, never runtime mathematical decisions. Poisoning expected
failure text and authored conclusions leaves all five changed analyses equal.
Publication tests compare staged and published mathematics excluding review.

The frontend adds the classification contract and explicit classification
comparison label; all reported facts still come from the backend. Component,
real HTTP and Edge checks cover a known missing derivative, the locally valid
punctured identity, changed classification and the unchanged positive control.
No new page, state library, inference layer or public challenge was introduced.

## Verification

Before publication, the scoped second-batch run passed 76 tests (56 runtime /
contract cases plus 20 independent mathematical cases) in 17.38s. The subsequent
full staging run passed 496 tests in 77.79s. The only initial two scoped failures
were missing remediation on the second-quadrant scalar mismatch; adding a
generic checker-owned repair resolved them without changing mathematical
verdicts. All fifteen direct and real-spawn scenarios match the approved labels,
outcomes, first-invalid positions, comparison bases and well-formedness.

Final acceptance results obtained after publication:

| Command | Actual result |
| --- | --- |
| uv run --frozen pytest -q --tb=short | 514 passed, 82.79s; one existing Starlette/HTTPX deprecation warning |
| npm.cmd test | 49 passed, 2.67s |
| npm.cmd run typecheck | Passed |
| npm.cmd run build | Passed including typecheck; JS 558.38 kB / 169.66 kB gzip; existing chunk advisory |
| npm.cmd run test:integration | 9 passed, 17.91s; actual Vite proxy / FastAPI / spawn workers |
| npm.cmd run test:browser | 18 passed, 54.6s; actual installed Edge, desktop 1440x1000 and mobile 390x844 |

No timeout/concurrency limit has been relaxed. The extra publication regression
compares staged and reviewed production mathematics. Frontend fixtures were
refreshed through actual API/spawn execution for all eleven templates; they are
test-only data. One initial component test assumed Step 1 was selected after
navigation, whereas the existing inspector selects the first invalid step
(Step 2). Explicitly selecting Step 1 repaired that test without changing app
selection behavior.

As an additional check against the prior root cause, all fifteen new direct
scenarios and two actual spawn/API zero-parameter cases also run with the
deterministic adverse SymPy assumption order. This separate 17-case run passed
in 3.77s; it exercises the new raw-domain paths while retaining the original
fourteen repair regressions. No production RNG behavior was changed.

The earlier published-library run passed 497 tests in 79.09s; the final 514-test
run includes those additional seventeen adverse-order cases. The batch-02
runtime file now contributes 74 cases; its twenty independent mathematical
checks were already part of the accepted 440-test baseline.

The in-app browser failed before execution with missing sandboxPolicy, so
actual browser acceptance used installed Edge. All four new desktop/mobile
cusp/classification screenshots were visually inspected; they are retained
under frontend/test-results (ignored by Git). Whole-page width checks passed.
The development servers used for acceptance were stopped before final backend
regression, avoiding overlapping computation load.

Final inventory check: eleven templates, ten reviewed. Neither acceptance port
8000/5173 remains listening. Inspecting all exported analyses found a largest
JSON of 17,059 UTF-8 bytes with ordinary spacing, conservatively larger than
compact worker serialization; the largest baseline worker request is 6,619
bytes. Both are below the unchanged 65,536-byte message cap. The real-worker
tests/export also exercised every declared second-batch change through that cap.

Tests also exercise wrong sine families/unbound inverse arguments; a claimed
punctured identity with its restriction removed; a wrong derivative formula;
unsupported derivative/classification families; forged limit components;
the absent-premise/equal-limit case; missing two-sided neighborhoods; typed
classification versus LaTeX poisoning; model scopes and extra orders; unchanged
parser grammar; actual deadline termination; and publication consistency.

## Remaining scope

This is a finite verifier, not a general proof system. The point-derivative
rule supports only the stated square-root family at zero with a full real
domain. Stationary classification supports the stated real polynomial degrees.
Rational limit checks use finite real points and finite-boundary neighborhoods;
the L'Hopital rule supports the stated affine two-sided 0/0 case only. Other
families and unresolved facts return Unknown rather than a guessed verdict.
There is no infinity-over-infinity theorem implementation, arbitrary high-order
differentiation or general ODE solving.

Ten more reviewed templates (including formal integral re-review), three extra
Mode C samples, final eight-domain coverage QA and final environment documentation
remain in Phase 5. Python 3.13/3.14 and Termux have not been tested. Desktop and
mobile browser viewports are not physical Android/Termux verification. The
unchanged three-second Windows spawn deadline can yield Unknown/Indeterminate
on loaded machines. Existing RAM-quota/sandbox limits and build warnings remain.
