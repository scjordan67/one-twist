# Phase 5.1: capability inventory and proposed typed contracts

Update 2026-10-18: Claude Code approved this design and batch 01 mathematics.
The subset required by 01-05 is now implemented and published following actual
isolation/API acceptance. The inventory below records the preimplementation
checkpoint; remaining proposed specs are still design only. See
[batch 01 implementation](batch-01-implementation.md) and
[batch 02 drafts](batch-02-review.md).

The approved 06-10 subset is now also implemented and published; see
[batch 02 implementation](batch-02-implementation.md). Later IVP/complex/vector
and extended-integral proposals below remain design-only.

Prepared 2026-10-18. This is a design and authoring checkpoint, not a runtime
implementation or content approval. No new checker, public template, API or
frontend behavior is introduced. The first five review packets are in
batch-01/*.json; they are outside the production loader and package data.

## Capability inventory

| Area | Current capability | Required finite extension |
| --- | --- | --- |
| Parsing | Bounded arithmetic AST, literal powers, sqrt/log/trig, exact numbers | Keep grammar and budgets; construct derivatives, limits, arg and vectors only in trusted checker code |
| Computation | EquationSpec and IntegralSpec | Closed scalar values, point limits/derivatives, stationary-point classification, two IVP families, principal argument, vector angle and 3D line intersection |
| Equation domains | Real/integer, retained denominators and predicates | Named mutable domain conditions; scoped complex-polynomial solving without real inequalities |
| Step checks | Equation transformation, affine substitution, antiderivative and scalar evaluation | Whole-expression real definedness, candidate acceptance, principal inverse branch; later the specific theorem/ODE/geometry rules below |
| Assumptions | Parameter predicates and real closed-interval continuity | Quantified predicates on the actual admissible domain; later finite differentiability/theorem/ODE facts |
| Perturbations | Listed parameter changes; removing an assumption changes its status | Domain/boundary choices must change owned mathematical facts; replacing a premise is distinct from declaring it false |
| Integrals | Separate endpoint limits; interior singularities return Unknown | Split the reviewed rational integrand at its interior singularity; never combine divergent pieces into a principal value |
| Reports | Independent dimensions; numeric/solution-set/divergent/undefined/unknown results | Formula, property and classification results; comparison with an appropriate basis |
| Isolation/API | Spawn, two shared slots, 3 s including startup, JSON 64 KiB | Reuse unchanged; inspect per-template payload sizes; no new worker operation or arbitrary callable |

The inventory is based on app/models/domain.py, engine/context.py,
perturbation.py, assumptions.py, verifier.py and classifier.py. Declaring
variables complex currently does not make the real-domain solver support them.
Likewise, a perturbation type appearing in a Literal is not an implemented
operation.

## Computation discriminators

All proposed models inherit the existing Model (extra=forbid). Expr below means
MathExpression, whose non-null source is validated by the unchanged parser.
Spec dispatch remains an explicit dictionary/discriminated union. JSON cannot
provide a Python callable, import, class name or new operation implementation.

| kind | Proposed fields | Established result / restriction |
| --- | --- | --- |
| equation (existing) | variable, left: Expr, right: Expr | Complete/partial/conditional solution set, with actual domains |
| integral (existing) | variable, integrand, lower, upper | Finite real value or divergence from separate limits |
| scalar_expression | expression: Expr; value_domain: real or complex | Closed finite scalar after node-level definedness; unresolved variables are Unknown |
| limit | variable; expression: Expr; point: Expr; direction: left/right/both | Two-sided result requires compatible one-sided results; initially finite real approach points |
| derivative_at_point | variable; expression: Expr; point: Expr | First derivative only; existence checked from difference quotients, including domain/side behavior |
| stationary_point | variable; expression: Expr; point: Expr | Initially reviewed real cubics/quadratics; classify local_minimum/local_maximum/stationary_non_extremum, not just f'' |
| first_order_ivp | independent_variable; dependent_variable; rhs: Expr; initial_time/value: Expr; time_domain; question: solution/uniqueness; candidate_solutions: bounded list[Expr] | Initially y'=y and y'=2sqrt(y) on the reviewed domains, not arbitrary ODE solving |
| principal_argument | expression: Expr; branch: negative_pi_open_positive_pi_closed | Nonzero finite complex input; Arg(0) undefined; no arithmetic arg call accepted from input |
| vector_angle | u, v: fixed length 2 or 3 tuples of Expr | Closed finite real vectors; zero vector makes requested angle undefined |
| line_intersection_3d | first, second: {origin, direction: 3-tuples of Expr} | Nonzero directions; solve all three component equations, not a projection |

Derivative and stationary-point operations do not accept arbitrary high orders.
Vector entries are scalar expressions, not matrix Python syntax. IVP candidate
counts and vector dimensions have fixed small bounds. The dependent variable in
rhs and time variable in candidate formulas have distinct validated symbol scopes.
ODE substitution checks residual, initial value, regularity and the declared
time domain; dsolve is not called.

For IVP uniqueness, candidates are only witnesses. Uniqueness needs the finite
family's actual proof conditions, including forward existence on t>=0 for the
sqrt family at a=1. At a=0, verifying both y=0 and y=t^2 disproves uniqueness;
the response must not describe them as an exhaustive solution family.
The checker must verify the rhs belongs to its supported family, not trust an
authored family name as evidence.

Reference validation must dispatch by kind. Existing loader/evaluator accesses
to computation.variable cannot be applied to vector/IVP specs. Symbols, scopes,
parameters, conditions and references are validated before publication.

## Result and comparison semantics

Keep the existing result statuses and completeness rules. Add only:

- symbolic_formula: established solution formula, with its domain stated.
- property: a typed boolean for a named question, initially uniqueness.
- classification: a finite enum, initially stationary-point classification.

Proposed additional fields are property_name/property_value and classification,
with status-dependent validation; absent fields remain null. Scalar values are
not used to encode true/false or editorial category names. Formula comparison
uses symbolic_formula; property/classification comparisons add matching basis
values to ConclusionComparison. Existing numeric_value and symbolic_formula
requests remain valid.
For these new bases, original/perturbed MathExpression fields remain display
representations only. Compute changed from the typed outcome values in
original_outcome/perturbed_outcome, never from LaTeX or a numeric cast of a
boolean/classification. The old established-value validator must be extended
to require the appropriate typed payload for each new status.

Problem well_formedness and requested quantity existence remain distinct.
For example, sqrt(x^2) is a defined function even though its derivative at zero
does not exist; this must not be described as an undefined function. Likewise,
a nonunique IVP is not automatically no-solution or contradictory.

The conclusion dimension continues to refer to the independently obtained
answer to the current problem. It is not an endorsement of an unrepaired
step's claimed answer. Review packets therefore explicitly separate
reference_outcome from derivation_claim.

## Domain and boundary ownership

Proposed additions, with existing fields retained for old templates:

~~~~text
DomainSpec:
  number_system: real | complex | integer
  constraints: list[Predicate]

DomainConditionBinding:
  kind: domain
  variable: Identifier
  current: DomainSpec

DomainChoice:
  id: Identifier
  domain: DomainSpec

Condition:
  existing parameter_name/predicate fields
  domain_binding: DomainConditionBinding | null

PerturbationRule:
  existing parameter fields and allowed_values
  domain_choices: list[DomainChoice]

Perturbation:
  existing fields
  choice_id: Identifier | null
~~~~

For type=domain, require an offered choice_id and new_value=null. For parameter
changes require an offered new_value and choice_id=null; removal of a premise
requires neither. Reject mixed payloads. An offered domain choice replaces
exactly the condition-owned domain. It cannot edit arbitrary JSON paths.
Templates cannot bind two independent mutable domain conditions to the same
variable in this MVP.

The effective domain is the intersection of the number system, fixed problem
domain_constraints, condition-owned constraints, and intrinsic expression
definedness. Derived problem.variables entries must agree with the authoritative
condition number system; synchronize them atomically on a real-to-complex
change. Step restrictions remain separate and cannot shrink a transformation's
input solution set retroactively.
Real ordering predicates are rejected on complex domains; changing number
systems does not grant complex numbers an ordering.

For the 02/04 baseline snapshots, original_problem.domain_constraints currently
contains the reviewed baseline restriction. Their review packet's domain_condition
identifies that exact owned group. On conversion to the proposed runtime schema,
MOVE it into Condition.domain_binding.current; do not retain a second fixed copy.
The expanded-domain scenario explicitly has no such restriction.

Boundary choices later use the same ownership principle, with a bounded
IntervalDomainSpec (lower/upper Expr, independent left_closed/right_closed
booleans). A boundary rule changes one declared endpoint or one closure flag,
not unrelated interval properties. Replacing a premise uses offered server-side
predicate choices, not an instruction to assert an arbitrary predicate.
Removing an assumption changes its status; it does not silently widen the
problem's mathematical domain.

## First-batch rule parameters

Existing equation_transform and evaluate_expression are reused where correct.
The proposed types below belong to two discriminated unions: step
RuleParameters adds expression_identity, candidate_acceptance, evaluate_scalar
and solve_candidates; Assumption.check uses domain_predicate and
candidate_predicate. The two assumption checks are not step-invalid checkers.

~~~~text
DomainPredicateParameters:
  operation: domain_predicate
  variable: Identifier
  required: Predicate

ExpressionIdentityParameters:
  operation: expression_identity
  left, right: Expr
  value_domain: real | complex

CandidateAcceptanceParameters:
  operation: candidate_acceptance
  candidates_from: EquationSpec
  original: EquationSpec

RealEvaluationParameters:
  operation: evaluate_scalar
  expression: Expr
  value_domain: real | complex

SolveCandidatesParameters:
  operation: solve_candidates
  equation: EquationSpec

CandidatePredicateParameters:
  operation: candidate_predicate
  variable: Identifier
  candidates_from: EquationSpec
  required: Predicate
~~~~

Assumption gains an optional check member, a discriminated union of
DomainPredicateParameters and CandidatePredicateParameters for this batch.
Old parameter nonzero/log_argument predicates retain their existing behavior.
The review packet's planned_assumption_checks maps the proposed member to its
assumption ID explicitly; a checker never discovers its scope from prose.
In 03 the sign predicate is quantified over the complete squared candidate
set, not all real x. In 02/04 the predicates are quantified over the admitted
problem domain. Completeness/undefinedness failures produce Unknown rather
than a guessed satisfied/violated state.
Violation of either assumption predicate only supplies evidence. Step failure
still needs an actual undefined operation, solution-set mismatch or verified
counterexample. The JSON packets keep these checks exclusively in
planned_assumption_checks rather than duplicating them as step verdict rules.

Domain-predicate checks quantify over the actual problem domain, not just a
supplied candidate. Use set inclusion and a computed counterexample when
available; unresolved inclusion is Unknown. This checks x!=2 for 02 and x>=0
for 04 without inventing a general inverse-function prover.

Candidate acceptance compares the complete candidate set with the independently
solved original equation in its original domain, or checks candidates plus
exhaustiveness. Partial sets cannot establish a complete original answer.
Squaring is checked as OneWayImplication; extra candidates alone do not make
the forward squaring step invalid.

Real expression evaluation/identity must check the unevaluated expression tree
before simplification. In 05, log(t*t) at t=-1 is real and defined, while
2*log(t) has an undefined real-log node. It is not enough to inspect whether
the final simplified value happens to be real. No implicit switch to complex
logarithms is permitted. The scalar computation of the original expression
does not reuse the invalid split as its derivation.

Later rule names/parameter members will be finalized in their corresponding
batch: finite trig branch coverage/quadrant checks; difference quotients and
second-derivative/limit theorem guards; separate interior-integral limits and
repeated-pole forms; ODE substitution and witnesses; principal-argument wrapping;
vector normalization and all-component line intersection. No checker is
implemented merely because its operation is listed here.

## Authoring packet versus runtime template

The five JSON files are review packets, not drop-in Template JSON. They reuse
the existing Problem/Assumption/Method/Step structures for baseline snapshots
and provide proposed_computation, planned_checks, domain_condition,
allowed_changes, and scenarios as explicitly private authoring material.
These additions are specified above rather than prematurely wired into the
accepted production models. No extra general-purpose authoring model hierarchy
or runtime interpreter is introduced at this checkpoint.

Scenario expected reports, reference sets and mathematical bases are author
claims for independent review and regression tests. They must never be used by
a worker to manufacture verdicts. Only approved executable spec/parameters and
actual checker evidence will be compiled into the eventual runtime templates.
Publication also requires the future runtime/API tests, not just passing these
independent content checks.

## Execution sequence

1. Review this design and all five mathematical packets.
2. After explicit content approval, implement only the contracts/checkers needed
   for 01-05, with compatibility and real isolation/API tests.
3. Record the actual reviewer and move approved templates into the production
   directory only after runtime acceptance. Keep stable existing IDs.
4. Continue the remaining batches in order. The existing integral template is
   formally reviewed in batch 11-15; it remains draft now.
