# Phase 5 batch 02 (06-10): mathematical drafts for independent review

Runtime update: all five approved packets have now been implemented, passed
real isolated API acceptance, and entered the public library with reviewed /
Claude Code records. See [implementation and verification](batch-02-implementation.md).
The draft-stage statements below record the original review submission.

Update 2026-10-18: Claude Code independently approved the mathematics of all
five packets. Runtime implementation was paused to resolve the batch-01 radical
baseline failure; see [the root-cause report](batch-01-radical-fix.md). The JSON
packets still record their original draft state and are not published runtime
templates. No further mathematical approval of this submitted scope is pending.

Prepared 2026-10-18 after the first batch's implementation and publication.
All five packets in batch-02 remain draft/reviewer=null, outside the loader.
No new second-batch checker or public template is implemented. Reusing the
already implemented scalar identity operation in 07 is not publication.

| No. | Packet | Main change | Legal control |
| --- | --- | --- | --- |
| 06 | [sine-principal-branch](batch-02/06-sine-principal-branch.json) | $c:1\to1/2$ | Upper interval bound $b:2\pi\to\pi$, keeping $c=1$ |
| 07 | [cosine-quadrant-sign](batch-02/07-cosine-quadrant-sign.json) | $\theta:\pi/3\to2\pi/3$ | $\theta=\pi/6$ |
| 08 | [derivative-cusp](batch-02/08-derivative-cusp.json) | $t:1\to0$ | $t=2$ |
| 09 | [stationary-second-derivative](batch-02/09-stationary-second-derivative.json) | $a:1\to0$ | $a=2$ |
| 10 | [lhopital-form](batch-02/10-lhopital-form.json) | $t:0\to1$, keeping $k=1$ | $k:1\to2$, keeping $t=0$ |

There are fifteen baseline/changed scenarios. The two added control parameters
make legal non-breaking changes available without changing the proposed main
counterexamples: 06 is initially exactly $[0,2\pi)$, and 10 is initially exactly
$x/(x+t)$. Each scenario changes only one condition. Baseline step output
notation in every packet is a baseline claim, not a frozen runtime answer.

## 06 — principal inverse and missing sine solutions

Solve $\sin x=c$ on $0\le x<b$, initially $c=1,b=2\pi$.
Step 1 claims the equivalent equation $x=\arcsin c$; Step 2 evaluates that
chosen root; Step 3 claims it is the complete answer.

| Parameters | Complete original roots | Principal-branch claim | First invalid |
| --- | --- | --- | --- |
| $c=1,b=2\pi$ | $\{\pi/2\}$ | Same | None |
| $c=1/2,b=2\pi$ | $\{\pi/6,5\pi/6\}$ | $\{\pi/6\}$ | principal-inverse (Step 1) |
| $c=1,b=\pi$ | $\{\pi/2\}$ | Same | None |

The general sine solutions include both $\arcsin c+2n\pi$ and
$\pi-\arcsin c+2n\pi$. At $c=1$ these branches coincide in the stated interval;
at $c=1/2$ they do not. Check all periods against the actual half-open interval.
Step 2 remains a locally correct evaluation after the branch loss, while the
Step 3 completeness claim is false. The premise concerns coverage of the
actual equation's roots, not global injectivity of sine on the whole interval.

Expected method: Invalid Step for the missing-branch scenario, otherwise Valid.
The independent equation answer is Valid + Changed Conclusion only for $c=1/2$.
The shorter-interval control changes a condition without changing the answer.
Repair by retaining both inverse branches and relevant periods.

Proposed narrow parameters: principal_sine_inverse/evaluate_principal_sine/
principal_sine_completeness. The checker must validate that the actual equation
is $\sin x=c$ with a closed real rhs and a supported interval, not trust an
operation name as proof of this form. Construct asin in trusted code; do not
add arbitrary inverse-function calls to the arithmetic grammar.

## 07 — quadrant sign

Evaluate $\cos\theta$ through the identity
$\cos^2\theta=1-\sin^2\theta$, initially $\theta=\pi/3$.
Step 1 rearranges the Pythagorean identity; Step 2 selects the positive root;
Step 3 evaluates that positive root.

| $\theta$ | Actual cosine | Positive-root value | First invalid |
| --- | --- | --- | --- |
| $\pi/3$ | $1/2$ | $1/2$ | None |
| $2\pi/3$ | $-1/2$ | $1/2$ | choose-positive-root (Step 2) |
| $\pi/6$ | $\sqrt3/2$ | $\sqrt3/2$ | None |

The square root equals $|\cos\theta|$ for these real angles. Only the sign
selection step fails in quadrant II; the identity and evaluation of the
positive root remain valid calculations. Method: Invalid Step only there.
Both nonbaseline angles change the independent numeric conclusion. The
nonnegative-cosine premise is a pointwise parameter predicate, not an immutable
domain condition that would make the quadrant-II problem contradictory.
The first-batch scalar computation/identity/evaluation rules can be reused.

## 08 — punctured derivative formula versus a point derivative

Let $f_t(x)=\sqrt{x^2+t^2}$ and determine the existence/value of $f_t'(0)$.
The function is real and defined for every real $x,t$.
Step 1 establishes $f_t'(x)=x/\sqrt{x^2+t^2}$ **on $x\ne0$**.
Step 2 evaluates the formula at the requested point.

| $t$ | Left difference-quotient limit | Right limit | Point derivative |
| --- | --- | --- | --- |
| $1$ | $0$ | $0$ | $0$ |
| $0$ | $-1$ | $1$ | Does not exist |
| $2$ | $0$ | $0$ | $0$ |

For $t>0$, rationalize:

$$
\frac{\sqrt{h^2+t^2}-t}{h}
=\frac{h}{\sqrt{h^2+t^2}+t}\longrightarrow0.
$$

For $t=0$ the original quotient is $|h|/h$, giving the two unequal limits.
The punctured derivative identity remains valid on both sides at $t=0$;
its retained $x\ne0$ restriction must not remove the requested point from the
problem. Step 2 is the first invalid step (substitute-at-zero), since it tries
to use $0/0$. Even for the baseline, the punctured identity alone is not proof
of the derivative at zero: independently verify the original difference quotient.

The independent requested-quantity outcome is undefined at $t=0$, but the
problem/function is WellFormed. This is a known nonexistence result, not Unknown.
The conclusion dimension refers to that established result (Valid + Changed
Conclusion); it does not endorse the original Step 2 claim of a zero derivative.
The control $t=2$ has all steps Valid and an unchanged derivative value.

Proposed parameters: derivative_identity_on_domain and
derivative_point_substitution, associated with DerivativeAtPointSpec.
The point-formula premise has explicit variable/point/formula scope. No generic
high-order differentiation or continuity-of-derivative shortcut is required.

## 09 — zero second derivative is inconclusive, not proof of a non-extremum

Classify the stationary point $0$ of $f_a(x)=x^3+ax^2$.
Steps: establish $f'_a(0)=0$; compute $f''_a(0)=2a$; claim a strict local minimum
using the positive second-derivative test.

For $a=1$ and the control $a=2$, $2a>0$ and the point is a strict local minimum.
Independently,
$f_a(x)-f_a(0)=x^2(x+a)>0$ for $0<|x|<a/2$.
At $a=0$, derivatives are still computed correctly, but $f''(0)=0$ does not
justify Step 3. The independent proof that the claimed minimum is false is
$f_0(h)=h^3>0$ and $f_0(-h)=-h^3<0$ for every $h>0$.
The point is stationary_non_extremum (also an inflection point).

First invalid: claim-local-minimum (Step 3), with method Invalid Step and
remediation to use signs/neighborhood values. This labels the **false
authored minimum claim**. A standalone second-derivative test at zero is merely
inconclusive; its failed sufficient condition alone must not cause this verdict.
The classification changes only for $a=0$. Reference/claimed classifications
use typed classification fields, not numeric values or LaTeX comparison.

StationaryPointSpec is initially limited to the reviewed real polynomial
families. Proposed checks separately establish stationarity, compute the
second derivative and compare the claimed classification with independent
local behavior.

## 10 — L'Hopital form

Initially evaluate $\lim_{x\to0}x/(kx+t)$ with $k=1,t=0$.
Step 1 differentiates numerator/denominator: $N'=1,D'=k$.
Step 2 replaces the quotient limit with the derivative-ratio limit.
Step 3 evaluates $1/k$.

| $(t,k)$ | Original limit | Derivative-ratio limit | First invalid |
| --- | --- | --- | --- |
| $(0,1)$ | $1$ | $1$ | None |
| $(1,1)$ | $0$ | $1$ | replace-quotient-limit (Step 2) |
| $(0,2)$ | $1/2$ | $1/2$ | None |

At $t=0$, numerator/denominator both tend to zero, are differentiable on the
punctured neighborhood, and $D'=k\ne0$. L'Hopital applies; the punctured original
quotient also simplifies independently to $1/k$. At $t=1,k=1$, the denominator
tends to $1$, so ordinary limit laws give zero, while mechanically differentiating
still gives one. Derivative identities and evaluation of $1/k$ remain correct;
the limit replacement is false. Method: Invalid Step only for this main change.
Both nonbaseline scenarios change the true numeric answer.

The extra coefficient $k$ supplies a genuinely legal non-breaking change,
not another disguised invalid example. The reviewed rule initially checks the
zero-over-zero form at a finite point; it does not claim support for every
infinity-over-infinity or oscillatory case. LimitSpec must use punctured-domain
semantics: an undefined expression exactly at the approach point does not make
its limit undefined.

## Next gate

Independent tests in `tests/test_phase5_batch02_math.py` verify the exact root
sets, quadrant values, one-sided quotients, local-value witnesses, and
original/derivative-ratio limits. The actual scoped run passed all 20 tests;
the subsequent full backend run passed 426 tests. Their success supports this
review but does not approve new content or prove
runtime implementation. After explicit mathematical approval, implement only
the necessary additional typed spec/checker members and repeat real isolation/
API/UI acceptance before publication.
