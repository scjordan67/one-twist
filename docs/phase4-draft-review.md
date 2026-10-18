# Phase 4.1–4.2: contracts and sample drafts for independent review

**Subsequent approval, 2026-10-17:** Claude Code independently approved all five
samples and ten configurations, reran all 268 tests and authorized publication
and Phase 4.3–4.4. Their review records now say reviewed / Claude Code. This
packet is preserved as the historical pre-approval submission; implementation
and current results are in [Phase 4 notes](phase4-report.md).

Original checkpoint, prepared 2026-10-17: **All 5 samples and 10 challenge configurations remain draft;
every reviewer field is null.** This document requests review; it records no
approval. No grader, challenge HTTP route, frontend integration or live sample
publication has been implemented in this delivery. The existing grading endpoint
continues to return 501.

## Files and scope

- [Challenge contracts](../app/models/challenges.py): mode-discriminated answers
  and authored configurations, sample/rubric models, public allowlist DTOs and
  the future feedback response shape.
- [Challenge loader](../app/challenges/loader.py): validates all drafts for audit,
  and exposes only reviewed configurations through its public accessors. A
  reviewed Mode C configuration cannot reference a draft sample.
- [Sample JSON](../app/challenges/data/samples): five self-contained problems,
  methods, premises, proposed steps, private annotations, complete accepted
  answer tuples, mathematical bases and repairs.
- [Challenge JSON](../app/challenges/data/challenges): two Mode A, three Mode B,
  five Mode C configurations. The two original template files are unchanged.
- [Contract tests](../tests/test_challenge_contracts.py) and
  [independent content checks](../tests/test_challenge_sample_math.py).

The preliminary ChallengeAnswer/AIDerivationSample contracts now live in the
challenge module and remain exported from `app.models`. Domain Grade and the
existing Problem/Assumption/Method/Step models are reused. The shared arithmetic
source validator in the template loader was given a public name for reuse;
its parsing behavior is unchanged. Package data includes the new JSON files.

## Proposed request and publication contracts

The three answer models discriminate on `mode` and reject extra fields:

| Mode | Required fields beyond mode/challenge_id |
| --- | --- |
| A | step_id, assumption_id, reason_category |
| B | perturbation |
| C | derivation, conclusion, step_id, assumption_id, reason_category |

All permit optional `free_text`, bounded to 4,000 characters, solely for later
echoing; no storage, code execution or semantic scoring is attached to it.

For C, `derivation` is `sound` or `not_sound` **as written on the stated domain**;
the cause is expressed by `reason_category`. This avoids forcing a student to
distinguish two overlapping labels such as "invalid" and "missing condition".
`conclusion` independently accepts `correct`, `incorrect`, `not_established`.
The four sample categories are private content organization, not the student's
answer options or an automatic grading rule.

A sound response uses `reason_category=no_flaw`, `step_id=null`,
`assumption_id=null`. A flaw needs a step; an assumption may be null when not
applicable. The same no-flaw shape is permitted as a Mode A student's answer;
it is not silently converted to an empty selection. Cross-mode fields and
client-supplied grade/evidence/rubric fields are forbidden.

A sample rubric contains either complete accepted tuples **or** an explicit
unknown reason and no accepted tuples. Unknown grading standards are not negative
answer keys. A reviewed, mathematically underdetermined conclusion can instead
have an established `not_established` answer: this is distinct from an unknown
rubric. There is no grading implementation in this delivery.

Public details contain stated problem information and the proposed mathematical
steps, not their annotations. Specifically:

- Problem projection excludes well_formedness and computation specs.
- Step projection includes only id/number/input/output/method_id and the claimed
  transformation kind. It excludes verification, explanation, premise links and
  private domain requirements. Stated problem domain constraints remain visible.
- Method projection includes only id and name.
- Premise choices contain id and neutral description, without state or checks.
- Category, rubric, actual_conclusion, annotations, remediation and review are
  never included in exercise details. The proposed/claimed conclusion in C is
  intentionally visible because students must assess it.
- All C samples use the same eight reason options, three premise options with
  neutral IDs, three displayed steps, and neutral sample/challenge titles.
  Choices are not filtered by accepted answers.
- Reviewed publication requires a named reviewer. Tests use synthetic in-memory
  review identities only; no checked-in content has been marked reviewed.

Future GET endpoints will consume the loader's public accessors. Until approval
and Phase 4.3 wiring, the bank is not attached to application startup or routes.
Calling `load_challenges(load_templates()).public_summaries()` currently yields
an empty list, and public detail access returns None for every draft.

## Sample 001 — private category: correct

Source: [sample-001.json](../app/challenges/data/samples/sample-001.json).
Real equation (ax=1), with the stated parameter (a=2).

| Step | Proposed result | Claimed relation |
| --- | --- | --- |
| 1 | (ax=1, a=2 \Rightarrow 2x=1) | Equivalent under the given parameter |
| 2 | (2x=1 \Rightarrow x=\tfrac12) | Equivalent |
| 3 | (x=\tfrac12 \Rightarrow S=\{\tfrac12\}) | Equivalent solution description |

Proposed accepted tuple:
`(sound, correct, null, null, no_flaw)`.

Audit basis: 2 is nonzero, so division is reversible on the real numbers. The
candidate satisfies the original equation, and the reversible linear chain
exhausts its solutions. Neither nonnegative/integer candidate restrictions need
to be supplied as a repair. No repair is proposed.

## Sample 002 — private category: correct

Source: [sample-002.json](../app/challenges/data/samples/sample-002.json).
Evaluate (I=\int_0^{3/4}(1-x)^{-1}\,dx), using (u=1-x).

| Step | Proposed result | Claimed relation |
| --- | --- | --- |
| 1 | (I=\int_{1/4}^{1}u^{-1}\,du) | Equivalent affine substitution with reversed limits |
| 2 | (I=\log 1-\log(1/4)) | Equivalent endpoint evaluation |
| 3 | (I=\log 4) | Equivalent simplification |

Proposed accepted tuple:
`(sound, correct, null, null, no_flaw)`.

Audit basis: on ([0,3/4]), (1-x\ge1/4>0), so the original integral is proper
and its integrand continuous. The affine substitution has derivative -1, with
bounds 1 and 1/4; reversing those bounds removes the minus sign. On ([1/4,1])
the real logarithm is defined, differentiates to (1/u), and has finite endpoint
values. The exact value is log 4. No improper-integral repair is needed.

## Sample 003 — private category: missing_condition

Source: [sample-003.json](../app/challenges/data/samples/sample-003.json).
Simplify (f(x)=\sqrt{x^2}) for **every real x**, using the principal nonnegative
real square root.

| Step | Proposed result | Proposed private finding |
| --- | --- | --- |
| 1 | (f(x)=\sqrt{x\cdot x}) | Valid |
| 2 | (f(x)=x) | Missing sign condition; first flaw |
| 3 | (\forall x\in\mathbb R,\ \sqrt{x^2}=x) | False universal conclusion |

Proposed accepted tuple:
`(not_sound, incorrect, step-002, premise-001, missing_sign_condition)`.
Here premise-001 is (x\ge0); other choices are (x\ne0) and (x\le0).

Audit basis: the correct expression over the stated domain is (|x|), because
it is nonnegative and squares to (x^2). At x=-1, the proposed identity has sides
1 and -1. Thus the all-real conclusion is **incorrect**, not merely unverified
by the tool. The claimed identity is true exactly for x>=0; zero is allowed, so
"nonzero" is not the missing condition. Repair by using abs(x), or explicitly
restrict the claimed identity to the nonnegative domain.

## Sample 004 — private category: wrong_derivation_right_answer

Source: [sample-004.json](../app/challenges/data/samples/sample-004.json).
Solve (2x=2) over all reals. Each displayed Equivalent relation explicitly
claims equal real solution sets, with **no additional sign constraint retained**.

| Step | Proposed transformation | Real solution sets | Proposed finding |
| --- | --- | --- | --- |
| 1 | (2x=2 \iff x=1) | \{1\} → \{1\} | Valid |
| 2 | (x=1 \iff x^2=1) | \{1\} → \{-1,1\} | Invalid; first flaw |
| 3 | (x^2=1 \iff x=1) | \{-1,1\} → \{1\} | Invalid |

Proposed accepted tuples:

- `(not_sound, correct, step-002, premise-001, irreversible_squaring)`
- `(not_sound, correct, step-002, premise-001, extraneous_root)`

Premise-001 requires the reverse implication when squaring is called an
equivalence. Nonzero/integer restrictions do not repair that implication, since
-1 satisfies both restrictions and remains an extra candidate.

Audit basis: the original equation has exactly x=1. Step 2 introduces -1;
its reverse implication is false. Step 3 silently drops -1 by using x instead
of abs(x) for the principal square root. Its equivalence is also false. These
two set errors happen to cancel, leaving the correct final answer x=1. Correct
final output does not validate the chain. Step 3 alone is not the first flaw.
The simplest repair is to stop after dividing by two; otherwise the directions
of implication and any candidate checks must be stated correctly.

## Sample 005 — private category: flawed

Source: [sample-005.json](../app/challenges/data/samples/sample-005.json).
Solve (\sqrt{x}=x-2) over the reals, with the stated radical domain (x\ge0).

| Step | Proposed transformation | Proposed finding |
| --- | --- | --- |
| 1 | (\sqrt{x}=x-2 \Rightarrow x=(x-2)^2) | Valid **one-way implication** |
| 2 | (x=(x-2)^2 \iff (x-1)(x-4)=0 \iff x\in\{1,4\}) | Valid solution of the squared equation |
| 3 | (S_{\mathrm{original}}=\{1,4\}) | Invalid acceptance of candidates; first flaw |

Proposed accepted tuples:

- `(not_sound, incorrect, step-003, premise-001, extraneous_root)`
- `(not_sound, incorrect, step-003, premise-001, missing_sign_condition)`

Premise-001 requires checking the original equation, including (x-2\ge0).
The other choices (x\ge0) and (x\ne0) do not exclude the extra candidate 1.

Audit basis: Step 1 is explicitly a necessary condition, so squaring itself is
not the first invalid step. Expanding gives (x^2-5x+4=0), whose roots 1 and 4
both meet the radical's domain. But x=1 gives original sides 1 and -1, while x=4
gives 2 and 2. Every original solution must be among the polynomial roots, so
this check also proves exhaustiveness: the true solution set is exactly \{4\}.
Repair by retaining (x\ge2) for the reverse implication, or by checking both
candidates in the original equation.

## Mode A/B configuration review

| IDs | Configuration |
| --- | --- |
| practice-001 | A, linear template, a=0; first division step, nonzero premise, zero_divisor |
| practice-002 | A, integral template, b=1; original **proper-integral** argument; first substitution step, regular interval or positive-u premise, improper_endpoint |
| practice-003 | B, linear template; goal invalidate_original_derivation |
| practice-004 | B, integral template; goal invalidate_original_derivation |
| practice-005 | B, linear template; goal change_conclusion |
| practice-006…010 | C, samples 001…005 respectively |

A accepted entries retain full step/premise/reason tuples. Every entry requires
all its evidence matches; an acceptable tuple needs a verification rule bound
to that step. The integral alternatives require their respective violated-premise
evidence in addition to the computed improper_required result. A later grader
must also require the runtime first-invalid field to be established; these keys
are not a substitute for calculation or a use of expected_failure_mechanisms.

For B, finite changes a=2/-1 and b=3/4 must fail the invalid-derivation goal even
though their conclusions change. The a=0/b=1 cases meet that goal; b=1 still
allows a repaired method. Under the change-conclusion goal, a=2 succeeds while
the method stays valid. These are proposed acceptance expectations; no grader
has been written or tested here.

## Verification and remaining gate

Actual runs:

- `uv run --frozen pytest tests/test_challenge_contracts.py tests/test_challenge_sample_math.py -q`:
  **66 passed**, 0.81s.
- `uv run --frozen pytest -q`: **268 passed**, one existing Starlette/HTTPX
  deprecation warning. This includes all 202 previously accepted tests.

Contract tests cover discriminators, cross-mode/client-verdict rejection,
required/null fields, explicit unknown standards, complete tuples, IDs and
references, canonical declared perturbations, parser rejection of unsafe/unknown
sources, reviewer identity, draft publication gating and public metadata
filtering. A poisoning test confirms private annotations, remedy, actual answer,
category, verification and explanatory text cannot change the public projection.
Another test forbids engine/worker execution while loading and presenting content.

Content tests pin the displayed formulas and independently compute solution
sets, exact integral values, the radical counterexample and both extraneous/lost
root mechanisms using SymPy. They do not parse LaTeX or validate arbitrary
external derivations. Their passing is supporting evidence for this review,
not a substitute for the requested independent mathematical audit.

Frontend files and dependencies are unchanged and their tests were not rerun.
No services were started for this data/model-only delivery. Phase 4.3 grading,
Phase 4.4 UI and HTTP integration remain untouched. After approval, record the
actual reviewer before allowing publication and proceeding to those stages.
