"""Finite real equation, integral, branch and calculus checks; worker-only."""

from dataclasses import dataclass, field

import sympy as sp

from app.engine.context import Context, UnsupportedMath, equal_sets, math_expression, subset, truth
from app.engine.calculus import affine_components, finite_limit, lhopital_data, point_derivative, stationary_facts, real_point
from app.engine.integrals import simple_pole, component_primitive, interior_contributions, two_pole_facts
from app.engine.ivp import ivp_facts, candidate_valid, verified_reference, verified_nonuniqueness
from app.models.domain import (
    AntiderivativeCheck, ConclusionResult, DimensionResult, EquationSpec,
    EquationTransform, EvaluationCheck, Evidence, IntegralSpec, MathExpression,
    Step, SubstitutionCheck, TransformationKind, ValidityLabel, VerificationRule,
    WellFormedness,
    ScalarExpressionSpec, ExpressionIdentityCheck, ScalarEvaluationCheck,
    SolveCandidatesCheck, CandidateAcceptanceCheck,
    DerivativeAtPointSpec, StationaryPointSpec, LimitSpec, PrincipalSineCheck,
    EvaluatePrincipalSineCheck, DerivativeIdentityCheck, DerivativePointSubstitutionCheck,
    StationaryValueCheck, ClaimStationaryClassificationCheck, DifferentiateLimitComponentsCheck,
    LHopitalReplacementCheck, EvaluateLimitCheck, FirstOrderIVPSpec,
    PrimitiveComponentsCheck, ProperEndpointCheck, TwoPoleAnsatzCheck, TwoPoleCoefficientsCheck,
    TwoPolePrimitiveCheck, TwoPoleEndpointCheck, LinearDivisionCheck, LinearLogCheck,
    LinearInitialCheck, IVPCandidateCheck, SqrtSubstitutionCheck, SqrtIntegrationCheck, InitialRootCheck,
    RootRateCheck,
)


@dataclass
class Solutions:
    value: sp.Set
    completeness: str
    undefined: bool = False


def solution_completeness(value: sp.Set) -> str:
    if isinstance(value, sp.ConditionSet):
        return "conditional"
    return "partial" if value.has(sp.ConditionSet) else "complete"


def solve_equation(spec: EquationSpec, context: Context, constraints=()) -> Solutions:
    variable = context.symbols[spec.variable]
    variable_domain = context.problem.variables[spec.variable]
    if variable_domain == "complex":
        raise UnsupportedMath("Complex equation domains are not supported in Phase 2")
    domain = context.domain(spec.left, variable) & context.domain(spec.right, variable) & context.admissible_domain(variable)
    if variable_domain == "integer":
        domain &= sp.S.Integers
    for predicate in constraints:
        domain &= context.constraint_set(predicate, variable)
    if domain is sp.S.EmptySet:
        return Solutions(sp.S.EmptySet, "complete", undefined=True)
    expression = context.expr(spec.left) - context.expr(spec.right)
    if expression.has(sp.zoo, sp.nan, sp.oo, -sp.oo):
        return Solutions(sp.S.EmptySet, "complete", undefined=True)
    value = sp.solveset(expression, variable, domain=domain)
    return Solutions(value, solution_completeness(value))


@dataclass
class ProblemEvaluation:
    result: ConclusionResult
    value: sp.Basic | None = None
    well_formedness: WellFormedness | None = None
    evidence: list[Evidence] = field(default_factory=list)


def unknown_outcome(reason: str) -> ProblemEvaluation:
    return ProblemEvaluation(ConclusionResult(status="unknown", reason_if_unknown=reason))


def integral_regularity(spec: IntegralSpec, context: Context) -> bool | None:
    variable = context.symbols[spec.variable]
    domain = context.domain(spec.integrand, variable)
    for predicate in context.constraints(variable):
        # Transformed integrals have their own variable; original-variable
        # restrictions are checked against the original integral separately.
        symbols = context.predicate(predicate).free_symbols
        if symbols <= {variable}:
            domain &= context.constraint_set(predicate, variable)
    return subset(context.interval(spec), domain)


def _integral(spec: IntegralSpec, context: Context) -> ProblemEvaluation:
    variable = context.symbols[spec.variable]
    interval = context.interval(spec)
    lower, upper = context.expr(spec.lower), context.expr(spec.upper)
    if lower == upper:
        raise UnsupportedMath("Zero-length integral conventions are outside Phase 2")
    domain = context.domain(spec.integrand, variable)
    for predicate in context.constraints(variable):
        domain &= context.constraint_set(predicate, variable)
    if subset(sp.Interval.open(interval.start, interval.end), domain) is not True:
        left, right = interior_contributions(context)
        if left is not -sp.oo or right is not sp.oo:
            raise UnsupportedMath("Separate simple-pole divergences were not established")
        return ProblemEvaluation(
            ConclusionResult(status="divergent", value=MathExpression(latex=r"\text{Divergent (opposing one-sided infinities)}")),
            well_formedness=WellFormedness.DIVERGENT,
            evidence=[Evidence(rule_id="split-interior-pole", outcome="opposing_infinities",
                               summary=f"Independent left piece tends to {left}; independent right piece tends to {right}. The ordinary integral diverges; no principal value or signed total is used.")],
        )
    integrand = context.expr(spec.integrand)
    primitive = sp.integrate(integrand, variable)
    if primitive.has(sp.Integral) or sp.simplify(sp.diff(primitive, variable) - integrand) != 0:
        raise UnsupportedMath("Antiderivative could not be verified")
    # Anchor at a regular interior point. Take both endpoint contributions
    # separately: opposing infinities must never cancel into a principal value.
    middle = (lower + upper) / 2
    anchored = primitive - primitive.subs(variable, middle)
    forward = truth(lower < upper) is True
    upper_limit = sp.limit(anchored, variable, upper, dir="-" if forward else "+")
    lower_limit = -sp.limit(anchored, variable, lower, dir="+" if forward else "-")
    contributions = [sp.simplify(upper_limit), sp.simplify(lower_limit)]
    if any(item.has(sp.Limit, sp.Integral, sp.nan, sp.zoo) for item in contributions):
        raise UnsupportedMath("An endpoint limit remains unresolved")
    divergent = [item for item in contributions if item in (sp.oo, -sp.oo)]
    if divergent:
        if len(set(divergent)) != 1:
            # The fact of divergence is known, but a signed infinite value is
            # not defined by adding the two divergent contributions.
            value = MathExpression(latex=r"\text{Divergent (opposing endpoint infinities)}")
            return ProblemEvaluation(ConclusionResult(status="divergent", value=value), well_formedness=WellFormedness.DIVERGENT)
        result = divergent[0]
        return ProblemEvaluation(
            ConclusionResult(status="divergent", value=math_expression(result)), result, WellFormedness.DIVERGENT,
        )
    result = sp.simplify(sum(contributions))
    if result.is_real is not True or result.is_finite is not True:
        raise UnsupportedMath("Integral value is not established finite and real")
    return ProblemEvaluation(
        ConclusionResult(status="numeric_value", value=math_expression(result)), result, WellFormedness.WELL_FORMED,
    )


def evaluate_problem(context: Context) -> ProblemEvaluation:
    try:
        spec = context.problem.computation
        if isinstance(spec, (EquationSpec, IntegralSpec)):
            admissible = context.admissible_domain(context.symbols[spec.variable])
            if admissible is sp.S.EmptySet:
                return ProblemEvaluation(
                    ConclusionResult(status="undefined", value=MathExpression(latex=r"\text{Contradictory conditions}")),
                    well_formedness=WellFormedness.CONTRADICTORY_CONDITIONS,
                )
        if isinstance(spec, EquationSpec):
            solution = solve_equation(spec, context, context.problem.domain_constraints)
            if solution.undefined:
                return ProblemEvaluation(
                    ConclusionResult(status="undefined", value=MathExpression(latex=r"\text{Undefined equation domain}")),
                    well_formedness=WellFormedness.UNDEFINED,
                )
            result = ConclusionResult(
                status="solution_set", value=math_expression(solution.value), completeness=solution.completeness,
                reason_if_unknown="solveset left unresolved conditions" if solution.completeness != "complete" else None,
            )
            formed = None if solution.completeness != "complete" else (
                WellFormedness.NO_SOLUTION if solution.value is sp.S.EmptySet else WellFormedness.WELL_FORMED
            )
            return ProblemEvaluation(result, solution.value, formed)
        if isinstance(spec, IntegralSpec):
            return _integral(spec, context)
        if isinstance(spec, FirstOrderIVPSpec):
            facts = ivp_facts(context)
            # The reported scope reflects the family the engine actually
            # established from the computed initial value, never the static
            # declared field: a perturbation can move a template between
            # families the single static solution_scope cannot track.
            established_scope = {"linear": "unique_solution", "sqrt": "verified_witness",
                                 "sqrt_zero": "nonuniqueness_witnesses"}[facts.family]
            if facts.family == "sqrt_zero":
                distinct, witnesses = verified_nonuniqueness(context, facts)
                if not distinct:
                    raise UnsupportedMath("Two pairwise distinct verified witnesses were not established")
                value = MathExpression(latex=r"\text{Not unique: } " + r"\text{ and }".join(sp.latex(item) for item in witnesses) + r"\text{ both solve it}")
                return ProblemEvaluation(
                    ConclusionResult(status="symbolic_formula", value=value,
                                     solution_scope=established_scope, variable=spec.independent_variable,
                                     time_domain=spec.time_domain),
                    None, WellFormedness.WELL_FORMED,
                    [Evidence(rule_id="ivp-nonuniqueness", outcome="distinct_witnesses_verified",
                              summary=facts.proof + f" Verified distinct solutions: {', '.join(sp.latex(item) for item in witnesses)}.")],
                )
            if not verified_reference(context, facts):
                raise UnsupportedMath("No declared candidate establishes the reference solution")
            return ProblemEvaluation(
                ConclusionResult(status="symbolic_formula", value=math_expression(facts.reference),
                                 solution_scope=established_scope, variable=spec.independent_variable,
                                 time_domain=spec.time_domain),
                facts.reference, WellFormedness.WELL_FORMED,
                [Evidence(rule_id="ivp-reference", outcome=established_scope, summary=facts.proof)],
            )
        if isinstance(spec, ScalarExpressionSpec):
            defined = context.definedness(spec.expression, spec.value_domain)
            if defined is False:
                return ProblemEvaluation(
                    ConclusionResult(status="undefined", value=MathExpression(latex=r"\text{Undefined in the declared value domain}")),
                    well_formedness=WellFormedness.UNDEFINED,
                )
            if defined is not True:
                raise UnsupportedMath("Scalar definedness or required values remain unresolved")
            value = context.expr(spec.expression)
            return ProblemEvaluation(ConclusionResult(status="numeric_value", value=math_expression(value)),
                                     value, WellFormedness.WELL_FORMED)
        if isinstance(spec, DerivativeAtPointSpec):
            facts = point_derivative(context, spec)
            if facts.value is None:
                return ProblemEvaluation(ConclusionResult(
                    status="undefined", value=MathExpression(latex=r"\text{Derivative does not exist}"),
                ), well_formedness=WellFormedness.WELL_FORMED)
            return ProblemEvaluation(ConclusionResult(status="numeric_value", value=math_expression(facts.value)),
                                     facts.value, WellFormedness.WELL_FORMED)
        if isinstance(spec, StationaryPointSpec):
            facts = stationary_facts(context, spec)
            return ProblemEvaluation(ConclusionResult(
                status="classification", classification=facts.classification,
                value=MathExpression(latex=r"\text{" + facts.classification.replace("_", " ") + "}"),
            ), well_formedness=WellFormedness.WELL_FORMED)
        if isinstance(spec, LimitSpec):
            facts = finite_limit(context, spec)
            value = math_expression(facts.value) if facts.value is not None else MathExpression(latex=r"\text{Two-sided limit does not exist}")
            return ProblemEvaluation(ConclusionResult(status=facts.status, value=value), facts.value,
                                     WellFormedness.DIVERGENT if facts.status == "divergent" else WellFormedness.WELL_FORMED)
        raise UnsupportedMath("No supported computation spec")
    except (UnsupportedMath, NotImplementedError, ValueError, TypeError, sp.PolynomialError) as exc:
        return unknown_outcome(str(exc))


@dataclass
class StepCheck:
    result: DimensionResult
    output: MathExpression | None = None
    input: MathExpression | None = None
    repairable: bool = False
    # Required in addition to repairable for symbolic IVP method repairs.
    repair_verified: bool = False


def verdict(rule: VerificationRule, label: ValidityLabel, outcome: str, summary: str, *, remediation=None, output=None, input=None, repairable=False, repair_verified=False) -> StepCheck:
    return StepCheck(DimensionResult(
        labels={label}, evidence=[Evidence(rule_id=rule.id, outcome=outcome, summary=summary)],
        affected_refs=rule.refs, reason_if_unknown=summary if label == ValidityLabel.UNKNOWN else None,
        remediation=remediation,
    ), output=output, input=input, repairable=repairable, repair_verified=repair_verified)


def _equation(rule: VerificationRule, step: Step, context: Context) -> StepCheck:
    params = rule.parameters
    assert isinstance(params, EquationTransform)
    if params.before.variable != params.after.variable:
        raise UnsupportedMath("Equation variable changes are not supported")
    if params.divisor is not None:
        divisor = context.expr(params.divisor)
        if divisor.is_zero is True:
            return verdict(rule, ValidityLabel.INVALID_STEP, "zero_divisor", "The computed divisor is zero; division is undefined.", remediation="Return to the original equation and split the zero-parameter case.")
    constraints = [*context.problem.domain_constraints, *step.domain_constraints]
    # A new restriction on the output cannot retroactively remove roots from
    # the input. Genuine input restrictions come from its syntax/problem.
    before = solve_equation(params.before, context, context.problem.domain_constraints)
    after = solve_equation(params.after, context, constraints)
    if before.undefined or after.undefined:
        return verdict(rule, ValidityLabel.INVALID_STEP, "undefined_equation", "A retained equation domain is undefined.")
    if before.completeness != "complete" or after.completeness != "complete":
        raise UnsupportedMath("Cannot compare partial or conditional solution sets")
    if step.transformation_kind == TransformationKind.CASE_SPLIT:
        raise UnsupportedMath("CaseSplit requires branch coverage, not just one pair of equations")
    equal = equal_sets(before.value, after.value)
    one_way = step.transformation_kind == TransformationKind.ONE_WAY_IMPLICATION
    valid = subset(before.value, after.value) if one_way else equal
    if valid is None:
        raise UnsupportedMath("Solution-set relation was not established")
    if not valid:
        added = after.value - before.value
        lost = before.value - after.value
        return verdict(rule, ValidityLabel.INVALID_STEP, "solution_set_changed", f"The transformation adds solutions {added} and loses solutions {lost}.", remediation="Retain excluded cases and check candidate solutions against the original equation.")
    equation = sp.Eq(context.expr(params.after.left), context.expr(params.after.right), evaluate=False)
    input_equation = sp.Eq(context.expr(params.before.left), context.expr(params.before.right), evaluate=False)
    return verdict(rule, ValidityLabel.VALID, "one_way_only" if one_way and equal is not True else "equivalent", "The complete solution sets satisfy the declared transformation direction.",
                   remediation="Check the reverse implication before accepting extra candidates." if one_way and equal is not True else None,
                   input=math_expression(input_equation), output=math_expression(equation))


def _substitution(rule: VerificationRule, step: Step, context: Context) -> StepCheck:
    params = rule.parameters
    assert isinstance(params, SubstitutionCheck)
    spec = context.problem.computation
    if not isinstance(spec, IntegralSpec):
        raise UnsupportedMath("Substitution requires an integral")
    x, u = context.symbols[spec.variable], context.symbols[params.transformed.variable]
    mapping = context.expr(params.mapping)
    polynomial = sp.Poly(mapping, x)
    if polynomial.degree() != 1 or polynomial.LC().is_zero is not False:
        raise UnsupportedMath("Only verified nonconstant affine substitutions are supported")
    derivative = sp.diff(mapping, x)
    mapped = context.expr(params.transformed.integrand).subs(u, mapping) * derivative
    identity = sp.simplify(mapped - context.expr(spec.integrand))
    bounds = [
        sp.simplify(mapping.subs(x, context.expr(spec.lower)) - context.expr(params.transformed.lower)),
        sp.simplify(mapping.subs(x, context.expr(spec.upper)) - context.expr(params.transformed.upper)),
    ]
    if identity != 0 or any(value != 0 for value in bounds):
        return verdict(rule, ValidityLabel.INVALID_STEP, "bad_substitution", "The computed Jacobian, transformed integrand or endpoints do not agree.")
    regular = integral_regularity(spec, context)
    transformed_regular = integral_regularity(params.transformed, context)
    if regular is False or transformed_regular is False:
        return verdict(rule, ValidityLabel.INVALID_STEP, "improper_required", "The affine identity holds, but the original proper-integral step includes a singular endpoint.", remediation="Truncate the interval before the singular endpoint, substitute there, then take the one-sided limit.", repairable=True)
    if regular is not True or transformed_regular is not True:
        raise UnsupportedMath("Closed-interval regularity was not established")
    output = sp.Integral(context.expr(params.transformed.integrand), (u, context.expr(params.transformed.lower), context.expr(params.transformed.upper)))
    return verdict(rule, ValidityLabel.VALID, "proper_substitution", "Affine identity, Jacobian, transformed bounds and both interval domains are verified.", output=math_expression(output))


def _antiderivative(rule: VerificationRule, step: Step, context: Context) -> StepCheck:
    params = rule.parameters
    assert isinstance(params, AntiderivativeCheck)
    spec = context.problem.computation
    if not isinstance(spec, IntegralSpec):
        raise UnsupportedMath("Antiderivative check requires an integral")
    variable = context.symbols[spec.variable]
    primitive = context.expr(params.primitive)
    if sp.simplify(sp.diff(primitive, variable) - context.expr(spec.integrand)) != 0:
        return verdict(rule, ValidityLabel.INVALID_STEP, "wrong_primitive", "Differentiation does not recover the integrand.")
    regular = integral_regularity(spec, context)
    if regular is False:
        return verdict(rule, ValidityLabel.INVALID_STEP, "endpoint_not_finite", "The derivative identity does not justify direct evaluation at a singular endpoint.", remediation="Replace endpoint substitution with separately evaluated one-sided limits.", repairable=True)
    if regular is None:
        raise UnsupportedMath("Closed-interval regularity was not established")
    output = sp.simplify(primitive.subs(variable, context.expr(spec.upper)) - primitive.subs(variable, context.expr(spec.lower)))
    if output.is_finite is not True or output.is_real is not True:
        raise UnsupportedMath("Primitive endpoint value is not established finite and real")
    return verdict(rule, ValidityLabel.VALID, "primitive_verified", "Differentiation and regular endpoint evaluation are verified.", output=math_expression(output))


def _evaluation(rule: VerificationRule, step: Step, context: Context) -> StepCheck:
    params = rule.parameters
    assert isinstance(params, EvaluationCheck)
    value = context.expr(params.expression)
    if context.raw(params.expression).free_symbols:
        return verdict(rule, ValidityLabel.NEEDS_CHECKING, "unbound_expression", "Additional variable values are required before numerical evaluation.")
    if value.has(sp.nan, sp.zoo, sp.oo, -sp.oo) or value.is_finite is False or value.is_real is False:
        return verdict(rule, ValidityLabel.INVALID_STEP, "undefined_expression", "Direct evaluation does not give a finite real value.", repairable=isinstance(context.problem.computation, IntegralSpec))
    if value.is_finite is None or value.is_real is None:
        raise UnsupportedMath("Expression definedness is unresolved")
    output = sp.Eq(context.symbols[params.result_variable], value, evaluate=False) if params.result_variable else value
    assignments = ", ".join(sp.latex(sp.Eq(symbol, number, evaluate=False)) for symbol, number in context.values.items())
    input_expression = MathExpression(latex=sp.latex(context.parse(params.expression)) + (r"\quad " + assignments if assignments else ""))
    return verdict(rule, ValidityLabel.VALID, "evaluated", "The expression is recomputed with the current parameters and retained restrictions.", input=input_expression, output=math_expression(output))


def _solve_candidates(rule: VerificationRule, step: Step, context: Context) -> StepCheck:
    params = rule.parameters
    assert isinstance(params, SolveCandidatesCheck)
    result = solve_equation(params.equation, context, step.domain_constraints)
    if result.undefined or result.completeness != "complete":
        raise UnsupportedMath("Candidate solving did not establish a complete, defined set")
    return verdict(rule, ValidityLabel.VALID, "complete_candidates",
                   "The complete candidate set is computed independently; it has not yet been accepted as the original answer.",
                   output=math_expression(result.value))


def _candidate_acceptance(rule: VerificationRule, step: Step, context: Context) -> StepCheck:
    params = rule.parameters
    assert isinstance(params, CandidateAcceptanceCheck)
    if params.original != context.problem.computation:
        raise UnsupportedMath("Candidate acceptance must refer to the actual original problem equation")
    candidates = solve_equation(params.candidates_from, context, step.domain_constraints)
    original = solve_equation(params.original, context)
    if any(item.undefined or item.completeness != "complete" for item in (candidates, original)):
        raise UnsupportedMath("Candidate acceptance requires two complete, defined solution sets")
    equal = equal_sets(candidates.value, original.value)
    if equal is None:
        raise UnsupportedMath("Candidate completeness comparison remains unresolved")
    if not equal:
        return verdict(rule, ValidityLabel.INVALID_STEP, "candidate_set_mismatch",
                       f"Accepted candidates add {candidates.value - original.value} and omit {original.value - candidates.value} from the original solution set.",
                       remediation="Check candidates in the original equation and include every admissible original branch or cancelled case.")
    return verdict(rule, ValidityLabel.VALID, "candidates_verified",
                   "The complete accepted candidate set equals the independently solved original equation.",
                   output=math_expression(original.value))


def _scalar_evaluation(rule: VerificationRule, step: Step, context: Context) -> StepCheck:
    params = rule.parameters
    assert isinstance(params, ScalarEvaluationCheck)
    if context.raw(params.expression).free_symbols:
        return verdict(rule, ValidityLabel.NEEDS_CHECKING, "unbound_expression", "Required scalar variable values have not been supplied.")
    defined = context.definedness(params.expression, params.value_domain)
    if defined is False:
        return verdict(rule, ValidityLabel.INVALID_STEP, "undefined_expression",
                       "An unevaluated intermediate is not finite or not in the declared value domain.",
                       remediation="Evaluate the original expression within its actual domain.")
    if defined is None:
        raise UnsupportedMath("Scalar intermediate definedness remains unresolved")
    return verdict(rule, ValidityLabel.VALID, "evaluated",
                   "Every intermediate is defined in the declared value domain before simplification.",
                   input=math_expression(context.raw(params.expression)), output=math_expression(context.expr(params.expression)))


def _expression_identity(rule: VerificationRule, step: Step, context: Context) -> StepCheck:
    params = rule.parameters
    assert isinstance(params, ExpressionIdentityCheck)
    expressions = (params.left, params.right)
    if any(context.raw(item).free_symbols for item in expressions):
        return verdict(rule, ValidityLabel.NEEDS_CHECKING, "unbound_expression", "Variable values are needed to check this scalar identity.")
    defined = [context.definedness(item, params.value_domain) for item in expressions]
    if False in defined:
        return verdict(rule, ValidityLabel.INVALID_STEP, "undefined_identity_side",
                       "A side of the proposed identity contains an undefined intermediate in the declared value domain.",
                       remediation="Evaluate the original expression directly, or justify a rewrite whose intermediate expressions are defined in the declared value domain.")
    if any(item is None for item in defined):
        raise UnsupportedMath("Identity intermediate definedness remains unresolved")
    equal = (sp.simplify(context.expr(params.left) - context.expr(params.right))).is_zero
    if equal is None:
        raise UnsupportedMath("The scalar identity remains unresolved")
    return verdict(rule, ValidityLabel.VALID if equal else ValidityLabel.INVALID_STEP,
                   "identity_verified" if equal else "identity_false",
                   "Both sides are defined and their exact values " + ("agree." if equal else "differ."),
                   input=math_expression(context.raw(params.left)), output=math_expression(context.expr(params.right)) if equal else None,
                   remediation=None if equal else "Use a rewrite that preserves the actual value; check any required sign or branch conditions.")


def principal_sine_data(context, equation):
    if context.problem.computation != equation:
        raise UnsupportedMath("Principal sine checks must reference the actual problem equation")
    variable = context.symbols[equation.variable]
    argument = context.expr(equation.right)
    interval = context.admissible_domain(variable)
    if context.expr(equation.left) != sp.sin(variable) or argument.free_symbols:
        raise UnsupportedMath("The actual equation must be sin(x)=a closed real constant")
    if argument.is_real is not True or argument.is_finite is not True:
        raise UnsupportedMath("Inverse-sine argument is not established finite and real")
    if not isinstance(interval, sp.Interval) or interval.start.is_finite is not True or interval.end.is_finite is not True:
        raise UnsupportedMath("Principal sine coverage currently requires a finite real interval")
    root = sp.asin(argument)
    if root.is_real is not True:
        raise UnsupportedMath("A real principal inverse is not defined for this argument")
    actual = solve_equation(equation, context)
    if actual.undefined or actual.completeness != "complete" or not isinstance(actual.value, (sp.FiniteSet, type(sp.S.EmptySet))):
        raise UnsupportedMath("Complete finite sine roots were not established")
    membership = truth(interval.contains(root))
    if membership is None:
        raise UnsupportedMath("Principal-root interval membership is unresolved")
    chosen = sp.FiniteSet(root) if membership else sp.S.EmptySet
    return root, chosen, actual.value


def _principal_sine(rule, step, context):
    params = rule.parameters
    assert isinstance(params, PrincipalSineCheck)
    root, chosen, actual = principal_sine_data(context, params.equation)
    equal = equal_sets(chosen, actual)
    if equal is None:
        raise UnsupportedMath("Principal inverse coverage is unresolved")
    output = math_expression(sp.Eq(context.symbols[params.equation.variable], root, evaluate=False)) if params.operation == "principal_sine_inverse" else math_expression(chosen)
    return verdict(rule, ValidityLabel.VALID if equal else ValidityLabel.INVALID_STEP,
                   "principal_covers_roots" if equal else "missing_sine_branches",
                   f"The complete original roots are {actual}; the selected principal branch gives {chosen}.",
                   output=output if equal else None,
                   remediation=None if equal else "Retain both inverse-sine branches and all relevant periods, then intersect with the actual interval.")


def _evaluate_principal_sine(rule, step, context):
    params = rule.parameters
    assert isinstance(params, EvaluatePrincipalSineCheck)
    if context.definedness(params.argument) is not True:
        raise UnsupportedMath("The inverse argument is not established defined")
    root = sp.asin(context.expr(params.argument))
    if root.is_finite is not True or root.is_real is not True:
        return verdict(rule, ValidityLabel.INVALID_STEP, "undefined_principal_inverse", "The selected real principal inverse is undefined.")
    return verdict(rule, ValidityLabel.VALID, "principal_evaluated",
                   "The chosen principal inverse is evaluated locally; this does not assert coverage of all roots.",
                   output=math_expression(root))


def _derivative_identity(rule, step, context):
    params = rule.parameters
    spec = context.problem.computation
    assert isinstance(params, DerivativeIdentityCheck)
    if not isinstance(spec, DerivativeAtPointSpec) or params.variable != spec.variable or params.expression != spec.expression:
        raise UnsupportedMath("Derivative identity must refer to the actual function and variable")
    facts = point_derivative(context, spec)
    domain = context.admissible_domain(facts.variable)
    for restriction in step.domain_constraints:
        domain &= context.constraint_set(restriction, facts.variable)
    if equal_sets(domain, sp.S.Reals - sp.FiniteSet(0)) is not True:
        raise UnsupportedMath("This derivative identity checker requires an explicit nonempty punctured domain")
    if subset(domain, context.domain(params.claimed_derivative, facts.variable)) is not True:
        return verdict(rule, ValidityLabel.INVALID_STEP, "derivative_formula_domain", "The claimed derivative is not defined throughout the retained step domain.")
    h = sp.Dummy("h", positive=True)
    claimed = context.expr(params.claimed_derivative)
    for sign in (-1, 1):
        derivative = sp.diff(facts.function.subs(facts.variable, sign*h), h) * sign
        equal = sp.simplify(derivative - claimed.subs(facts.variable, sign*h)).is_zero
        if equal is None:
            raise UnsupportedMath("Derivative identity on a nonzero half-line is unresolved")
        if not equal:
            return verdict(rule, ValidityLabel.INVALID_STEP, "derivative_identity_false", "The claimed derivative differs on a punctured half-line.")
    return verdict(rule, ValidityLabel.VALID, "punctured_derivative_verified",
                   "Differentiation agrees on both nonzero half-lines; the retained restriction does not justify substitution at zero.",
                   output=math_expression(claimed))


def point_formula_status(context, params):
    spec = context.problem.computation
    if not isinstance(spec, DerivativeAtPointSpec) or params.variable != spec.variable or context.expr(params.point) != context.expr(spec.point):
        raise UnsupportedMath("Point substitution must refer to the actual derivative point")
    facts = point_derivative(context, spec)
    defined = truth(context.domain(params.formula, facts.variable).contains(facts.point))
    if defined is None:
        raise UnsupportedMath("Point-formula definedness is unresolved")
    return facts, defined


def _derivative_point(rule, step, context):
    params = rule.parameters
    assert isinstance(params, DerivativePointSubstitutionCheck)
    facts, defined = point_formula_status(context, params)
    if not defined or facts.value is None:
        return verdict(rule, ValidityLabel.INVALID_STEP, "invalid_point_substitution",
                       f"The formula is {'defined' if defined else 'undefined'} at the point; original difference-quotient limits are {facts.left} and {facts.right}.",
                       remediation="Compute the original one-sided difference quotients; a punctured derivative formula alone cannot be evaluated at an excluded point.")
    value = sp.simplify(context.expr(params.formula).subs(facts.variable, facts.point))
    equal = sp.simplify(value-facts.value).is_zero
    if equal is None:
        raise UnsupportedMath("Formula value versus point derivative is unresolved")
    return verdict(rule, ValidityLabel.VALID if equal else ValidityLabel.INVALID_STEP,
                   "point_derivative_verified" if equal else "point_derivative_mismatch",
                   f"Original left/right difference quotients give {facts.left}/{facts.right}; the formula gives {value}.",
                   output=math_expression(value) if equal else None)


def _stationary_value(rule, step, context):
    params = rule.parameters
    spec = context.problem.computation
    assert isinstance(params, StationaryValueCheck)
    if not isinstance(spec, StationaryPointSpec) or params.expression != spec.expression or params.variable != spec.variable or context.expr(params.point) != context.expr(spec.point):
        raise UnsupportedMath("Stationary calculation must refer to the actual function and point")
    # Independently compute the requested derivative even when the test is inconclusive.
    variable, point = real_point(context, spec.variable, spec.point)
    expression = context.expr(spec.expression)
    if not expression.is_polynomial(variable) or context.domain(spec.expression, variable) != sp.S.Reals:
        raise UnsupportedMath("This derivative-value checker requires a polynomial")
    order = 1 if params.operation == "stationary_point_check" else 2
    value = sp.simplify(sp.diff(expression, variable, order).subs(variable, point))
    valid = value.is_zero if order == 1 else value.is_finite
    if valid is None:
        raise UnsupportedMath("Stationary derivative value is unresolved")
    return verdict(rule, ValidityLabel.VALID if valid else ValidityLabel.INVALID_STEP,
                   "derivative_value_verified" if valid else "not_stationary",
                   f"The independently computed order-{order} derivative at the point is {value}.",
                   output=math_expression(value) if valid else None)


def _stationary_claim(rule, step, context):
    params = rule.parameters
    assert isinstance(params, ClaimStationaryClassificationCheck)
    spec = context.problem.computation
    if not isinstance(spec, StationaryPointSpec):
        raise UnsupportedMath("Stationary claim requires the actual stationary-point computation")
    facts = stationary_facts(context, spec)
    if params.classification != facts.classification:
        return verdict(rule, ValidityLabel.INVALID_STEP, "classification_false", facts.proof,
                       remediation="Use a first-derivative sign or neighborhood-value test when the second derivative vanishes.")
    if facts.second.is_zero is True:
        return verdict(rule, ValidityLabel.NEEDS_CHECKING, "second_derivative_inconclusive", facts.proof,
                       remediation="Justify the classification by neighborhood signs rather than the inconclusive second-derivative test.")
    return verdict(rule, ValidityLabel.VALID, "classification_verified", facts.proof,
                   output=MathExpression(latex=r"\text{" + facts.classification.replace("_", " ") + "}"))


def _limit_components(rule, step, context):
    params = rule.parameters
    assert isinstance(params, DifferentiateLimitComponentsCheck)
    numerator, denominator, variable, _ = affine_components(context, params)
    return verdict(rule, ValidityLabel.VALID, "component_derivatives_verified",
                   "The actual numerator and denominator are differentiated independently; this does not authorize replacing their quotient limit.",
                   output=MathExpression(latex=f"N'={sp.latex(sp.diff(numerator, variable))},\\quad D'={sp.latex(sp.diff(denominator, variable))}"))


def _lhopital(rule, step, context):
    params = rule.parameters
    assert isinstance(params, LHopitalReplacementCheck)
    form, ratio = lhopital_data(context, params)
    original = finite_limit(context, context.problem.computation)
    equal = False if original.value is None else truth(sp.Eq(original.value, ratio))
    if equal is None:
        raise UnsupportedMath("Original limit versus derivative-ratio value is unresolved")
    if not equal:
        return verdict(rule, ValidityLabel.INVALID_STEP, "limit_replacement_false",
                       f"The original limit is {original.value}; the derivative ratio is {ratio}. Zero-over-zero form: {form}.",
                       remediation="Check the original limiting form first; use ordinary limit laws when the denominator tends to a nonzero value.")
    if not form:
        return verdict(rule, ValidityLabel.NEEDS_CHECKING, "lhopital_form_missing",
                       "The two limits agree, but the required zero-over-zero form is absent.",
                       remediation="Justify the original limit using applicable limit laws instead of this theorem.")
    return verdict(rule, ValidityLabel.VALID, "lhopital_verified",
                   "Both components tend to zero, are affine and differentiable, and the denominator derivative is nonzero throughout the punctured neighborhood.",
                   output=math_expression(ratio))


def _evaluate_limit(rule, step, context):
    params = rule.parameters
    assert isinstance(params, EvaluateLimitCheck)
    actual = context.problem.computation
    if not isinstance(actual, LimitSpec) or params.variable != actual.variable or context.expr(params.point) != context.expr(actual.point):
        raise UnsupportedMath("Limit evaluation must use the actual variable and approach point")
    result = finite_limit(context, LimitSpec(variable=params.variable, point=params.point, expression=params.expression, direction=actual.direction))
    if result.value is None:
        return verdict(rule, ValidityLabel.INVALID_STEP, "two_sided_limit_missing", "The independently evaluated expression has incompatible one-sided limits.")
    return verdict(rule, ValidityLabel.VALID, "limit_evaluated",
                   "The displayed expression's limit is evaluated independently of the earlier replacement.",
                   output=math_expression(result.value))


def _primitive_components(rule, step, context):
    params = rule.parameters
    spec, x, _ = simple_pole(context)
    if isinstance(params, PrimitiveComponentsCheck) and params.variable != spec.variable:
        raise UnsupportedMath("Primitive variable must match the actual integral")
    valid = component_primitive(context, params.primitive)
    if not valid:
        return verdict(rule, ValidityLabel.INVALID_STEP, "wrong_component_primitive",
                       "The primitive identity or component domain does not match the actual integrand.")
    if isinstance(params, ProperEndpointCheck):
        regular = integral_regularity(spec, context)
        if regular is False:
            left, right = interior_contributions(context)
            return verdict(rule, ValidityLabel.INVALID_STEP, "unsplit_endpoint_formula",
                           f"The interior pole separates two divergent pieces ({left}, {right}); endpoint subtraction is not the ordinary integral.",
                           remediation="Replace the single-interval endpoint formula by two independent one-sided improper-integral limits.")
        if regular is not True:
            raise UnsupportedMath("Proper interval regularity remains unresolved")
    primitive = context.expr(params.primitive)
    output = primitive if isinstance(params, PrimitiveComponentsCheck) else sp.simplify(
        (primitive.subs(x, context.expr(spec.upper))-primitive.subs(x, context.expr(spec.lower))).doit())
    return verdict(rule, ValidityLabel.VALID, "component_primitive_verified",
                   "The primitive identity is verified on each separate component; the endpoint formula additionally requires a regular closed interval.",
                   output=math_expression(output))


def _two_pole(rule, step, context):
    params = rule.parameters
    facts = two_pole_facts(context)
    x, a = facts.x, facts.a
    if isinstance(params, TwoPoleAnsatzCheck):
        if params.variable != str(x):
            raise UnsupportedMath("Ansatz variable must match the actual integral")
        alpha, beta = (context.symbols[name] for name in params.coefficient_names)
        if sp.simplify((context.expr(params.ansatz)-(alpha/x+beta/(x-a))).doit()) != 0:
            return verdict(rule, ValidityLabel.INVALID_STEP, "wrong_ansatz", "The authored ansatz does not match the two reviewed constant-coefficient terms.")
    if not facts.solvable:
        return verdict(rule, ValidityLabel.INVALID_STEP, "collapsed_distinct_poles",
                       f"The actual constant-coefficient system has rank {facts.rank} and augmented rank {facts.augmented_rank}; no distinct-pole coefficients exist.",
                       remediation="Use alpha/x+beta/x^2, with alpha=0,beta=1; the verified primitive is -1/x on the regular integration interval.",
                       repairable=facts.repair_verified, repair_verified=facts.repair_verified)
    if isinstance(params, TwoPoleCoefficientsCheck):
        alpha = context.expr(params.coefficient_values["alpha"])
        beta = context.expr(params.coefficient_values["beta"])
        valid = sp.simplify((alpha+beta).doit()) == 0 and sp.simplify((-a*alpha-1).doit()) == 0
        output = sp.Tuple(alpha, beta)
    elif isinstance(params, TwoPolePrimitiveCheck):
        primitive = context.expr(params.primitive)
        lower = context.expr(context.problem.computation.lower)
        # The reviewed intervals lie to the right of both poles. Normalize
        # there before differentiating real absolute-value logarithms.
        if lower.is_positive is not True or (lower-a).is_positive is not True:
            raise UnsupportedMath("This partial-fraction primitive proof requires the reviewed right-of-poles interval")
        h = sp.Dummy("positive_offset", positive=True)
        restricted = sp.simplify(primitive.subs(x, lower+h).doit())
        valid = (sp.simplify((sp.diff(restricted, h)-facts.integrand.subs(x, lower+h)).doit()) == 0
                 and subset(context.interval(context.problem.computation), context.domain(params.primitive, x)) is True)
        output = primitive
    elif isinstance(params, TwoPoleEndpointCheck):
        value = context.expr(params.expression)
        actual = _integral(context.problem.computation, context)
        valid = context.definedness(params.expression) is True and sp.simplify((value-actual.value).doit()) == 0
        output = value
    else:
        valid, output = True, context.expr(params.ansatz)
    return verdict(rule, ValidityLabel.VALID if valid else ValidityLabel.INVALID_STEP,
                   "two_pole_verified" if valid else "two_pole_claim_false",
                   "Actual pole multiplicities, constant-coefficient equations and the claimed expression are recomputed.",
                   output=math_expression(output) if valid else None)


def _ivp(rule, step, context):
    params = rule.parameters
    facts = ivp_facts(context)
    # verified_reference needs a single reference formula; the nonuniqueness
    # family has none, so its own repair evidence comes from its witnesses.
    repaired = verified_nonuniqueness(context, facts)[0] if facts.family == "sqrt_zero" else verified_reference(context, facts)
    if isinstance(params, IVPCandidateCheck):
        valid, candidate, summary = candidate_valid(context, facts, params.candidate)
        return verdict(rule, ValidityLabel.VALID if valid else ValidityLabel.INVALID_STEP,
                       "ivp_candidate_verified" if valid else "ivp_candidate_false", summary,
                       output=math_expression(candidate) if valid else None,
                       remediation=f"Use the independently verified candidate {facts.reference} on the entire declared time domain." if not valid and repaired else None,
                       repairable=not valid and repaired, repair_verified=not valid and repaired)
    if isinstance(params, (LinearDivisionCheck, LinearLogCheck, LinearInitialCheck)):
        if facts.family != "linear":
            raise UnsupportedMath("A linear separation rule requires actual RHS y")
        if isinstance(params, LinearDivisionCheck):
            authored, expected = context.expr(params.divisor), facts.y
        elif isinstance(params, LinearLogCheck):
            authored, expected = context.expr(params.state_expression), sp.log(sp.Abs(facts.y))
        else:
            authored, expected = context.expr(params.expression), sp.log(sp.Abs(facts.initial))
        if isinstance(params, (LinearDivisionCheck, LinearLogCheck)) and sp.simplify((authored-expected).doit()) != 0:
            return verdict(rule, ValidityLabel.INVALID_STEP, "linear_separation_claim_false",
                           "The claimed divisor/logarithmic expression differs from the actual separation step.")
        if facts.initial == 0:
            return verdict(rule, ValidityLabel.INVALID_STEP, "zero_equilibrium_excluded",
                           "The original IVP has the verified zero solution, which division/logarithms exclude.",
                           remediation="Handle y=0 as a separate equilibrium case before division; verify it against the original ODE and initial value.",
                           repairable=repaired, repair_verified=repaired)
        if sp.simplify((authored-expected).doit()) != 0:
            return verdict(rule, ValidityLabel.INVALID_STEP, "linear_separation_claim_false", "The divisor or logarithmic expression differs from the actual linear separation step.")
        return verdict(rule, ValidityLabel.VALID, "linear_separation_verified",
                       "The integrating-factor proof establishes y=a*exp(t); nonzero initial state stays nonzero and retains its sign. " + facts.proof,
                       output=math_expression(authored))
    if facts.family not in ("sqrt", "sqrt_zero"):
        raise UnsupportedMath("A principal-root rule requires actual RHS 2*sqrt(y)")
    if isinstance(params, InitialRootCheck):
        if facts.family != "sqrt":
            raise UnsupportedMath("The principal-initial-root disambiguation applies only to the positive-state family")
        constant, root = context.expr(params.claimed_constant), sp.sqrt(facts.initial)
        valid = sp.simplify((constant-root).doit()) == 0
        return verdict(rule, ValidityLabel.VALID if valid else ValidityLabel.INVALID_STEP,
                       "initial_root_verified" if valid else "principal_initial_root_false",
                       f"The principal initial root is {root}; the claimed integration constant is {constant}.",
                       output=math_expression(root) if valid else None,
                       remediation="Choose C=sqrt(a^2)=abs(a), then verify the repaired candidate on the entire forward time domain." if not valid else None,
                       repairable=not valid and repaired, repair_verified=not valid and repaired)
    u = context.symbols[params.root_variable]
    if (u == facts.t or u == facts.y or context.problem.variables[params.root_variable] != "real"):
        raise UnsupportedMath("Root variable must be a distinct real auxiliary symbol")
    if isinstance(params, RootRateCheck):
        if facts.family == "sqrt_zero":
            return verdict(rule, ValidityLabel.INVALID_STEP, "zero_state_rate_excluded",
                           "The verified zero state makes u=sqrt(y)=0 at the initial time; dividing 2*u*u'=2*u by 2*u is invalid there.",
                           remediation="Verify the candidate solutions directly against the original ODE and initial value instead of dividing by u.",
                           repairable=repaired, repair_verified=repaired)
        return verdict(rule, ValidityLabel.VALID, "positive_root_rate_verified",
                       "The verified positive state keeps u=sqrt(y)>0, so dividing 2*u*u'=2*u by 2*u is valid.")
    if isinstance(params, SqrtIntegrationCheck) and facts.family == "sqrt_zero":
        return verdict(rule, ValidityLabel.INVALID_STEP, "zero_state_rate_excluded",
                       "Integrating u'=1 to u=t+C depends on the same division that is invalid at the verified zero state.",
                       remediation="Verify the candidate solutions directly against the original ODE and initial value instead.",
                       repairable=repaired, repair_verified=repaired)
    return verdict(rule, ValidityLabel.VALID, "positive_root_step_verified", facts.proof,
                   output=MathExpression(latex="2"+sp.latex(u)+sp.latex(u)+r"'=2"+sp.latex(u))
                   if isinstance(params, SqrtSubstitutionCheck)
                   else MathExpression(latex=sp.latex(u)+"="+sp.latex(facts.t)+r"+C"))


def _retained_constraints(rule: VerificationRule, step: Step, context: Context) -> StepCheck | None:
    params = rule.parameters
    if isinstance(params, PrimitiveComponentsCheck):
        spec, x, _ = simple_pole(context)
        for predicate in step.domain_constraints:
            if subset(context.domain(spec.integrand, x), context.constraint_set(predicate, x)) is not True:
                raise UnsupportedMath("Retained component restriction is not established on every integrand component")
        return None
    if isinstance(context.problem.computation, FirstOrderIVPSpec):
        facts = ivp_facts(context)
        for predicate in step.domain_constraints:
            relation = context.predicate(predicate).subs({facts.y: facts.reference})
            if isinstance(params, (SqrtSubstitutionCheck, SqrtIntegrationCheck, RootRateCheck)):
                relation = relation.subs(context.symbols[params.root_variable], facts.t+sp.sqrt(facts.initial))
            established = truth(sp.simplify(relation.doit()))
            if established is None and relation.free_symbols <= {facts.t}:
                established = subset(facts.domain, relation.as_set())
            if established is False:
                return verdict(rule, ValidityLabel.INVALID_STEP, "domain_violation", "The verified IVP solution does not satisfy a retained step restriction.")
            if established is not True:
                raise UnsupportedMath("A retained IVP step restriction remains unresolved")
        return None
    if isinstance(params, (EquationTransform, SolveCandidatesCheck, CandidateAcceptanceCheck, DerivativeIdentityCheck)):
        return None  # These checkers already enforce the retained step domain.
    interval = params.transformed if isinstance(params, SubstitutionCheck) else context.problem.computation
    for predicate in step.domain_constraints:
        relation = context.predicate(predicate)
        if isinstance(params, EvaluationCheck) and params.result_variable:
            relation = relation.subs(context.symbols[params.result_variable], context.expr(params.expression))
        established = truth(relation)
        if established is None and isinstance(interval, IntegralSpec):
            variable = context.symbols[interval.variable]
            if relation.free_symbols <= {variable}:
                established = subset(context.interval(interval), relation.as_set())
        if established is False:
            return verdict(rule, ValidityLabel.INVALID_STEP, "domain_violation", "A retained domain restriction is false.")
        if established is None:
            return verdict(rule, ValidityLabel.NEEDS_CHECKING, "unresolved_domain", "A retained domain restriction still requires verification.")
    return None


CHECKERS = {
    "equation_transform": _equation, "substitution": _substitution,
    "antiderivative": _antiderivative, "evaluate_expression": _evaluation,
    "expression_identity": _expression_identity, "evaluate_scalar": _scalar_evaluation,
    "solve_candidates": _solve_candidates, "candidate_acceptance": _candidate_acceptance,
    "principal_sine_inverse": _principal_sine, "principal_sine_completeness": _principal_sine,
    "evaluate_principal_sine": _evaluate_principal_sine,
    "derivative_identity_on_domain": _derivative_identity, "derivative_point_substitution": _derivative_point,
    "stationary_point_check": _stationary_value, "second_derivative_value": _stationary_value,
    "claim_stationary_classification": _stationary_claim,
    "differentiate_limit_components": _limit_components, "lhopital_replacement": _lhopital, "evaluate_limit": _evaluate_limit,
    "primitive_identity_on_components": _primitive_components, "proper_integral_endpoint_formula": _primitive_components,
    "two_pole_ansatz": _two_pole, "two_pole_coefficients": _two_pole, "two_pole_primitive": _two_pole, "two_pole_endpoint_value": _two_pole,
    "linear_ivp_division": _ivp, "linear_ivp_log_separation": _ivp, "linear_ivp_initial_constant": _ivp,
    "ivp_candidate_substitution": _ivp, "sqrt_ivp_substitution": _ivp, "sqrt_ivp_root_integration": _ivp, "ivp_principal_initial_root": _ivp,
    "sqrt_ivp_rate_division": _ivp,
}


def check_step(rule: VerificationRule, step: Step, context: Context) -> StepCheck:
    try:
        checker = CHECKERS.get(rule.kind)
        if checker is None or rule.parameters is None or rule.parameters.operation != rule.kind:
            raise UnsupportedMath(f"Unsupported or missing verification parameters for {rule.kind}")
        result = checker(rule, step, context)
        if ValidityLabel.VALID in result.result.labels:
            constraint_result = _retained_constraints(rule, step, context)
            if constraint_result is not None:
                return constraint_result
        return result
    except (UnsupportedMath, NotImplementedError, ValueError, TypeError, sp.PolynomialError) as exc:
        return verdict(rule, ValidityLabel.UNKNOWN, "unknown", str(exc) or "Symbolic rule could not establish a result")
