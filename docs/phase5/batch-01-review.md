# Phase 5 first batch: mathematical review packet

Update 2026-10-18: Claude Code independently approved all five detailed packets.
Their review records are now reviewed/Claude Code, and the corresponding
runtime templates have been implemented, tested and published. The text below
describes the historical submission. See
[implementation and actual acceptance results](batch-01-implementation.md).

Prepared 2026-10-18. All five packets are draft; reviewer=null. The accepted
Phase 5 coverage proposal is not treated as approval of these detailed drafts.
No new checker has been implemented and no draft has entered the public loader.
The existing linear-degeneration template is still draft, pending this formal
review; integral-endpoint will be resubmitted in batch 11-15.

See [the contract design and capability inventory](spec-design.md).
Files in batch-01 are structured review packets, not production Template JSON:

| No. | File | Subject |
| --- | --- | --- |
| 01 | [01-linear-degeneration.json](batch-01/01-linear-degeneration.json) | Existing parameter-degeneration example, formally resubmitted |
| 02 | [02-cancelled-factor-domain.json](batch-01/02-cancelled-factor-domain.json) | Illegal factor cancellation after widening a domain |
| 03 | [03-squared-candidates-sign.json](batch-01/03-squared-candidates-sign.json) | Correct forward squaring followed by incorrect candidate acceptance |
| 04 | [04-inverse-square-domain.json](batch-01/04-inverse-square-domain.json) | A principal inverse branch no longer covers the domain |
| 05 | [05-real-log-product.json](batch-01/05-real-log-product.json) | Invalid real logarithm splitting with an unchanged original answer |

Each packet includes the baseline Problem, Method, Step and Assumption objects,
allowed one-condition changes, explicit proposed computation/rule parameters,
scenario references, expected independent dimensions, mathematical grounds and
repairs. Scenario expectations are review/test data, never runtime evidence.
Snapshot domain restrictions for 02/04 must be moved to their named mutable
domain binding when converting to the proposed runtime schema; they are not
fixed constraints that survive a domain-widening change.

## 01 — parameter degeneration

Original: solve $ax=1$ over $\mathbb R$, initially $a=1$.
Step 1 divides by $a$; Step 2 evaluates $1/a$ with the current parameter.
Both retain $a\ne0$.

| $a$ | Complete original solution set | Steps / method | First invalid |
| --- | --- | --- | --- |
| $1$ baseline | $\{1\}$ | Valid / Valid | None |
| $2$ | $\{1/2\}$ | Valid / Valid | None |
| $-1$ | $\{-1\}$ | Valid / Valid | None |
| $0$ | $\varnothing$ | Both invalid / Invalid Step | divide-by-a |

At zero, the original equation is $0=1$, which is a well-defined equation with
no solutions. The quotient $1/0$ is instead undefined. Do not confuse these
two facts. Independently established new conclusions are Valid; they gain
Changed Conclusion for all three nonbaseline values. Comparison basis is
symbolic_formula (complete solution sets), not a guessed floating-point value.
Repair by returning to the original equation and separating $a=0$.

## 02 — cancellation and domain widening

Original: solve $(x-2)(x+1)=0$ with $x\in\mathbb R\setminus\{2\}$.
Steps: cancel $x-2$; solve $x+1=0$; claim the complete original set is $\{-1\}$.
The cancelled-factor restriction $x\ne2$ remains attached to the cancellation
step. It cannot be retroactively imposed on the input problem.

Only condition admissible-domain changes:

| Domain choice | Complete original solution set | Reused steps | Changed conclusion |
| --- | --- | --- | --- |
| $\mathbb R\setminus\{2\}$ baseline | $\{-1\}$ | All valid | No |
| $\mathbb R$ | $\{-1,2\}$ | Step 1 and completeness claim invalid; Step 2 locally valid | Yes |
| $(-\infty,2)$ control | $\{-1\}$ | All valid | No |

Zero-product reasoning establishes that the unrestricted roots are exactly
$-1$ and $2$. The widened domain admits $2$, but dividing removes it.
Step 2 is still a valid calculation on its own input; that does not establish
the completeness of the entire derivation. The first invalid step is
cancel-x-minus-two. The independent new solution set is Valid + Changed
Conclusion, while the authored method's present path has Invalid Step.
Repair by splitting $x=2$ and $x\ne2$, solving both cases and taking their union.

## 03 — squaring and extraneous candidates

To avoid duplicating sample-005, use $\sqrt x=x-c$ with **$c:0\to6$** instead
of perturbing to $2$. The fixed real domain is $x\ge0$.

1. Square forward: $\sqrt x=x-c\ \Longrightarrow\ x=(x-c)^2$.
   This step explicitly claims OneWayImplication.
2. Solve the squared equation completely, retaining $x\ge0$.
3. Accept every candidate as an original solution without checking the reverse
   implication. This is valid for the baseline, not for every perturbation.

| $c$ | Complete nonnegative candidate set | Complete original solution set | First invalid |
| --- | --- | --- | --- |
| $0$ baseline | $\{0,1\}$ | $\{0,1\}$ | None |
| $6$ | $\{4,9\}$ | $\{9\}$ | accept-all-candidates (Step 3) |
| $-1/4$ control | $\{1/4\}$ (double polynomial root) | $\{1/4\}$ | None |

At $c=6$ the polynomial is $x^2-13x+36=(x-4)(x-9)$. At $x=4$,
the original left/right values are $2$ and $-2$; at $x=9$ both equal $3$.
The reverse implication requires $x-c\ge0$. Thus
$\{4,9\}\cap[6,\infty)=\{9\}$.

At $c=-1/4$, the squared polynomial is $(x-1/4)^2$ and both original sides at
$x=1/4$ equal $1/2$. This gives a legal changed condition that preserves the
method, with a changed answer. Extra candidates make neither the forward
squaring nor complete polynomial solving invalid. The sign assumption is
quantified over candidates, not every $x$ in the input domain.

For $c=6$, steps 1/2 are Valid and Step 3 Invalid Step. The current authored
method has Invalid Step with a repair, while the independently established
problem conclusion $\{9\}$ is Valid + Changed Conclusion. This does not endorse
the unrepaired claim $\{4,9\}$. Repair by substitution or the sign restriction.

## 04 — inverse branch and injectivity

Let $f(x)=x^2$ with domain $[0,\infty)$ and solve $f(x)=y$ at the fixed value
$y=1$. Steps: apply the principal inverse $x=\sqrt y$; evaluate at $y=1$;
claim all preimages have been found.

| Domain choice | Complete preimage set | Reused steps | Changed conclusion |
| --- | --- | --- | --- |
| $[0,\infty)$ baseline | $\{1\}$ | All valid | No |
| $\mathbb R$ | $\{-1,1\}$ | Steps 1/3 invalid; evaluating the chosen root remains locally valid | Yes |
| $[1/2,\infty)$ control | $\{1\}$ | All valid | No |

On the original domain, for $0\le u<v$ we have
$v^2-u^2=(v-u)(v+u)>0$, proving injectivity. On $\mathbb R$,
$f(-1)=f(1)=1$ supplies an explicit failure of injectivity. The complete
equation solution set independently shows the lost negative root.
The problem remains meaningful after widening; there is simply no single-valued
inverse covering all its preimages. The first invalid step is
apply-principal-inverse. Repair by restoring the branch domain or keeping both
signed branches and intersecting with the actual problem domain.

This differs pedagogically from 02: one concerns an inverse function's domain
and branch completeness; the other concerns division by a factor.

## 05 — real logarithms and an unchanged answer

Task: evaluate the real expression $\log(t^2)$, initially $t=1$.
Steps: split into $2\log t$; evaluate that expression with the current parameter.
Parameter $t$ is real, not assumed positive as part of the problem domain.
Positivity is a premise of the proposed split, not a permanent condition of the
original task. The original expression's intrinsic domain is $t\ne0$.

| $t$ | Original value | Proposed split | Steps / method | Changed conclusion |
| --- | --- | --- | --- | --- |
| $1$ baseline | $0$ | $0$ | All valid / Valid | No |
| $-1$ | $0$ | Undefined over the reals | Both invalid / Invalid Step | No |
| $2$ control | $\log4$ | $2\log2=\log4$ | All valid / Valid | Yes |

The domain of $\log(t^2)$ is $\mathbb R\setminus\{0\}$; the domain of the split
real expression is $(0,\infty)$. At $t=-1$, the original product is $1$ and its
logarithm is $0$, but the intermediate $\log(-1)$ has no real value.
The requested original expression is still WellFormed; only the proposed
transformation/evaluation is invalid. The first invalid step is split-real-log.
The independent conclusion is Valid without Changed Conclusion.

Do not silently evaluate the real logarithm using a complex value and then
declare the expression valid. Definedness must be checked before simplification.
Repair by evaluating the original positive product directly, or by using
$2\log|t|$ with $t\ne0$.

## Interpretation and review gate

Invalid Step on the method dimension means that the currently authored flow
contains an invalid operation; it does not declare every repaired use of the
method impossible. The packets give repairs separately. Unknown is reserved
for genuinely unestablished verification, not for these proved counterexamples.
No Inconvenient label is inferred from cost.

Independent content tests are in tests/test_phase5_batch01_math.py. They use
direct SymPy calculations and explicit witnesses, not the new (unimplemented)
engine rules. They also check draft identities/references/sources and that public
content remains the two accepted-phase templates plus the existing challenges.
These tests do not prove runtime readiness or replace this requested review.

## Actual verification

Run on Windows on 2026-10-18:

| Command | Actual result |
| --- | --- |
| uv run --frozen pytest tests/test_phase5_batch01_math.py -q | 32 passed, 0.95s |
| uv run --frozen pytest -q | 345 passed (313 existing + 32 draft checks), 38.52s |

Both runs retain the one existing Starlette/HTTPX deprecation warning.
The final scoped run also verifies that premise checks live only in the
proposed assumption-check mapping, with mathematical step rules kept separate.
The 16 baseline/changed scenarios cover every offered change, including legal
controls. Root sets, set differences, injectivity witnesses, real logarithm
domains, exact values and comparison flags are computed independently of the
authored expectations.

The production app and frontend were not changed, and frontend checks were not
rerun for this design/content-only checkpoint. No new runtime checker, Pydantic
spec union, frontend control or public route is claimed implemented here.
Tests reuse existing core models for snapshot/reference validation; the new
typed contract proposals remain for review. No development servers were
started. Public GET checks show only the original two templates and ten
reviewed challenges; all five packets and both original templates remain draft.
