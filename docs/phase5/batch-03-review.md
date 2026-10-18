# Phase 5 batch 03 (11–15): mathematical drafts for independent review

Prepared 2026-10-18 following Claude Code's acceptance of batch 02.
This submission contains private review packets and independent mathematics
tests. It does not implement new runtime models/checkers, publish new templates,
or mark any content reviewed. The existing integral-endpoint review record
remains draft; its exact production snapshot is included for formal rereview.

| No. | Draft | Baseline | Main change and actual result | Valid control |
| --- | --- | --- | --- | --- |
| 11 | [integral-endpoint](batch-03/11-integral-endpoint.json) | \(b=1/2:\log2\) | \(b=1:+\infty\) | \(b=3/4:\log4\) |
| 12 | [integral-interior-pole](batch-03/12-integral-interior-pole.json) | \(c=2:-\log3\) | \(c=0:\) ordinary integral divergent, no signed total | \(c=3:-\log2\) |
| 13 | [integral-coalescing-poles](batch-03/13-integral-coalescing-poles.json) | \(a=1:\log(4/3)\) | \(a=0:1/6\), still a proper integral | \(a=-1:\log(9/8)\) |
| 14 | [ivp-zero-equilibrium](batch-03/14-ivp-zero-equilibrium.json) | \(a=1:y=e^t\) | \(a=0:y=0\) | \(a=2:2e^t;\ a=-1:-e^t\) |
| 15 | [ivp-principal-initial-root](batch-03/15-ivp-principal-initial-root.json) | \(a=1:y=(t+1)^2\) | \(a=-1:\) same IVP and repaired witness; unrepaired candidate fails | \(a=2:y=(t+2)^2\) |

There are sixteen scenarios. Each nonbaseline scenario changes exactly one
declared parameter condition. The JSON packets contain baseline Problem,
Assumption, Method and Step snapshots, allowed changes, planned finite checks,
reference outcomes, derivation claims and separate expected report dimensions.
Future IVP fields are private proposed_computation dictionaries, not accepted
members of the production ComputationSpec union.

## 11 — endpoint singularity: formal rereview of the existing template

\[
I(b)=\int_0^b\frac{dx}{1-x},\qquad u=1-x.
\]

For \(b<1\), the transformed interval stays away from zero and
\(I(b)=-\log(1-b)\). Thus the baseline is \(\log2\), and the regular
control is \(\log4\). At \(b=1\), use a truncated upper endpoint:

\[
\int_0^{1-\varepsilon}\frac{dx}{1-x}=-\log\varepsilon
\longrightarrow+\infty\quad(\varepsilon\downarrow0).
\]

The existing steps explicitly use the proper-integral substitution and
endpoint-evaluation procedure. At the singular endpoint all three of those
claims are invalid as written; the first is change-variable. The substitution
technique is recoverable on truncated intervals followed by the one-sided
limit, so the method is Needs Checking with that remediation. The independent
conclusion is Valid + Changed Conclusion, with well_formedness Divergent.
This does not claim that substitution itself is impossible for improper
integrals.

The packet includes the unchanged existing_template_snapshot. Stable template,
condition, assumption and step IDs must survive eventual implementation;
existing challenges must not be silently rebound to new IDs.

## 12 — an interior simple pole and an unrelated principal value

\[
J(c)=\int_{-1}^{1}\frac{dx}{x-c}.
\]

For \(c=2,3\), the integrand is continuous on the closed integration interval.
The primitive \(\log|x-c|\) gives respectively \(-\log3,-\log2\).
At \(c=0\), two independently truncated pieces are required:

\[
\int_{-1}^{-\varepsilon_L}\frac{dx}{x}=\log\varepsilon_L\to-\infty,
\qquad
\int_{\varepsilon_R}^{1}\frac{dx}{x}=-\log\varepsilon_R\to+\infty.
\]

Neither one-sided improper integral converges. The ordinary integral diverges;
there is no signed total and no cancellation of the two infinities.
Setting the two cutoffs equal gives symmetric principal value zero, but that
is a different question and is explicitly not the requested answer.

The primitive identity is valid on each separate component \(x\ne c\)
(Step 1). The unsplit endpoint formula is invalid (Step 2, first failure).
The scalar calculation
\(\log|1-c|-\log|-1-c|=0\) at \(c=0\) is itself valid (Step 3);
it does not establish the integral value.

Method scope is explicitly **single-interval endpoint evaluation**: Invalid
Step at the interior-pole scenario, with replacement by the split procedure
as remediation. This narrow procedure cannot be rescued by pretending its
global endpoint subtraction was legitimate. The independent conclusion is
Valid + Changed Conclusion; the problem is Divergent.

Proposed finite operations: primitive_identity_on_components,
proper_integral_endpoint_formula and existing scalar evaluation. Integral
evaluation must discover the actual interior singularity from the rational
integrand and bounds, split there, and combine only finite one-sided pieces.
Failure of a continuity premise alone is not proof that the answer diverges.

## 13 — repeated poles can break a decomposition without breaking the integral

\[
K(a)=\int_2^3\frac{dx}{x(x-a)}.
\]

The poles lie outside \([2,3]\) in every submitted scenario. For \(a\ne0\),
the distinct-pole ansatz with constant coefficients gives

\[
\frac1{x(x-a)}=\frac{\alpha}{x}+\frac{\beta}{x-a},\quad
\alpha+\beta=0,\quad -a\alpha=1.
\]

Thus \(\alpha=-1/a,\beta=1/a\), with primitive
\((\log|x-a|-\log|x|)/a\).
The values are \(\log(4/3)\) at \(a=1\) and \(\log(9/8)\) at \(a=-1\).
At \(a=0\), the coefficient equations have matrix rank 1 and augmented
rank 2: the distinct-pole ansatz has no solution. The repeated pole is at
zero, outside the integration interval, so the integral remains proper:

\[
K(0)=\int_2^3x^{-2}\,dx=[-1/x]_2^3=1/6.
\]

The first failure is the distinct-pole ansatz, followed by its coefficient,
primitive and endpoint steps. The broader **partial fractions** method has a
verified repair \(\alpha/x+\beta/x^2\), with \(\alpha=0,\beta=1\).
Method: Needs Checking with that repair; problem: WellFormed; conclusion:
Valid + Changed Conclusion. This is distinct from 12's divergent integral.

The distinct-pole expression is undefined at \(a=0\), even though its parameter
limit is \(1/6\). Taking that limit is a separate valid argument, not direct
substitution into the undefined expression.

Proposed checks verify the actual denominator family, multiplicities,
coefficient identity and repaired primitive. A JSON operation/family name
alone is not evidence. Coefficients are scalar constants, not functions of x.

## 14 — separation loses a zero equilibrium; negative controls retain sign

\[
y'=y,\qquad y(0)=a,\qquad t\in\mathbb R.
\]

For \(a\ne0\), separation gives \(y'/y=1\),
\(\log|y|=t+C\) and \(C=\log|a|\). Retaining the initial sign gives
\(y=a e^t\), including the negative control \(-e^t\).
The constraint \(y\ne0\) belongs to those steps, not to the original IVP.

At \(a=0\), division, logarithmic integration and logarithmic initial-value
substitution are invalid as a derivation of the zero solution. The first
failure is divide-by-state. An independent final substitution verifies
\(y=0\) against the original ODE and initial value; that step remains Valid.
The **separation of variables** method is Needs Checking: handle the zero
equilibrium as a separate case before dividing.

Existence follows from the explicit candidate. Uniqueness is independently
proved for every C1 solution on the connected real time domain:

\[
(e^{-t}y)'=e^{-t}(y'-y)=0.
\]

The integrating factor is constant and the initial condition fixes that
constant to a. Finding one solution is not used as a uniqueness proof.
The reference outcome is a symbolic_formula with scope unique_solution,
WellFormed throughout. Every nonbaseline control changes this solution.
No general dsolve or executable ODE syntax is proposed.

## 15 — the principal initial square root is |a|, not a

\[
y'=2\sqrt y,\qquad y(0)=a^2,\qquad t\ge0,\quad y\ge0.
\]

The request is one verified C1 forward solution, not uniqueness or a complete
solution family. All submitted a values are nonzero. For any admissible
solution, the RHS is nonnegative, so \(y(t)\ge y(0)=a^2>0\).
Consequently \(u=\sqrt y>0\), \(2uu'=2u\), and \(u'=1\) are legitimate on
the full forward domain. Integration gives \(u=t+C\).

The initial condition gives \(C=\sqrt{a^2}=|a|\).
At \(a=1,2\), writing C=a is correct. At \(a=-1\), the first failure is
choose-initial-root; C=a is false. The ensuing candidate \((t-1)^2\)
satisfies the initial value and is nonnegative, but fails the ODE on
\([0,1)\):

\[
y'-2\sqrt y=2(t-1)-2|t-1|=4(t-1)\quad(0\le t<1).
\]

At \(t=1/2\), the derivative is -1 and the RHS is 1. Validity on
\([1,\infty)\) cannot establish validity on the stated domain containing
the initial time. The repaired candidate \((t+|a|)^2\) satisfies the ODE,
initial condition, real-state restriction and C1 regularity throughout
\([0,\infty)\). Finite point checks can disprove a candidate; they cannot
establish its validity on the whole interval.

Method scope is **positive-root substitution**, Needs Checking with the
verified correction C=|a|. Steps 3 and 4 are Invalid at a=-1; steps 1 and 2
remain Valid. The independent reference witness is Valid.

**Intentional unchanged-problem control:** a=1 and a=-1 give the same IVP,
because a enters its initial value through a squared amplitude. The parameter
condition and reused derivation change, but the mathematical problem does
not. The repaired reference witness is the same \((t+1)^2\), so the
conclusion is unchanged despite the invalid reused derivation. This is
disclosed in the packet rather than described as a different IVP.
The a=2 control genuinely changes the initial state and reference witness.

This is not the later No. 16 uniqueness exercise. No. 16 remains reserved for
the loss of a Lipschitz sufficient condition and verified distinct zero-data
solutions. This batch does not claim uniqueness or enumerate a solution family
for the square-root ODE.

## Proposed contract boundaries, subject to this review

- Retain the existing integral spec; extend only the finite rational-integral
  operations required by 12/13.
- Future first_order_ivp has distinct independent/dependent symbols, RHS,
  initial time/value, time domain, state domain, question, solution_scope,
  and a small bounded candidate list. Unbounded time endpoints use null and
  cannot be marked closed. The initial time must belong to the time domain.
- For 14, time is all reals and state is real. For 15, time is [0,infinity)
  and state is nonnegative real. The two domains cannot be conflated.
- Establish the RHS family algebraically, independently of authored labels.
  Candidate sources use the existing arithmetic parser; derivatives and
  substitution are trusted checker operations, not new user-callable syntax.
- A symbolic_formula must distinguish unique_solution from verified_witness.
  Compare established formulas on their stated domain, not LaTeX or only the
  initial value. Do not present one witness as a complete solution set.
- Method repairs in 13–15 require computed supporting evidence. The current
  numeric/divergent repair branch cannot simply be generalized to all
  symbolic outcomes based on author-written remediation text.
- Unsupported family, unresolved identity/domain or exhausted computation
  remains Unknown. Existing request errors and worker failure semantics stay
  distinct from mathematical invalidity.

## Verification and approval gate

[Independent tests](../../tests/test_phase5_batch03_math.py) calculate
integrals, separate limits, denominator multiplicities, coefficient-system
ranks, primitive identities, ODE residuals, initial conditions, integrating
factor identities, forward-domain signs and typed conclusion comparisons.
They validate baseline snapshots/references and one-condition changes without
calling new engine code. They also prove the future IVP discriminator is not
accepted by the runtime schema.

The loading/GET check forbids worker execution, confirms the existing public
inventory is still 11 templates / 10 reviewed, confirms the four new IDs
return 404, and compares the legacy endpoint snapshot to its production file.

Actual scoped run: uv run --frozen pytest tests/test_phase5_batch03_math.py -q
— **25 passed**, one existing dependency deprecation warning, 0.96 seconds.
Full-suite run: uv run --frozen pytest -q --tb=short — **539 passed**,
one existing dependency deprecation warning, 87.91 seconds.
No frontend code changed; frontend/browser checks were not rerun for this
private mathematical-review submission.

After independent mathematical approval: implement the finite contracts and
checkers, exercise real isolated API cases, then publish reviewed records.
No runtime implementation or review promotion precedes this approval.
