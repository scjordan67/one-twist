"""Small function registry. Declared assumption state is never proof."""

from app.engine.context import Context, UnsupportedMath, subset, truth
from app.models.domain import Assumption, AssumptionResult, Evidence, IntegralSpec, EquationSpec, DomainPredicateCheck, CandidatePredicateCheck
from app.engine.verifier import solve_equation, principal_sine_data, point_formula_status
from app.engine.calculus import lhopital_data


def _predicate(assumption: Assumption, context: Context) -> bool | None:
    if assumption.predicate is None:
        return None
    if assumption.interval is None:
        return truth(context.predicate(assumption.predicate))
    variable = context.symbols[assumption.interval.variable]
    allowed = context.constraint_set(assumption.predicate, variable)
    return subset(context.interval(assumption.interval), allowed)


def _continuity(assumption: Assumption, context: Context) -> bool | None:
    spec = context.problem.computation
    if not isinstance(spec, IntegralSpec):
        raise UnsupportedMath("Continuity checker requires an integral spec")
    variable = context.symbols[spec.variable]
    return subset(context.interval(spec), context.domain(spec.integrand, variable))


def _domain_predicate(assumption: Assumption, context: Context) -> bool | None:
    params = assumption.check
    assert isinstance(params, DomainPredicateCheck)
    variable = context.symbols[params.variable]
    domain = context.admissible_domain(variable)
    spec = context.problem.computation
    if isinstance(spec, EquationSpec):
        domain &= context.domain(spec.left, variable) & context.domain(spec.right, variable)
    return subset(domain, context.constraint_set(params.required, variable))


def _candidate_predicate(assumption: Assumption, context: Context) -> bool | None:
    params = assumption.check
    assert isinstance(params, CandidatePredicateCheck)
    candidates = solve_equation(params.candidates_from, context)
    if candidates.completeness != "complete" or candidates.undefined:
        raise UnsupportedMath("Candidate predicate needs a complete, defined candidate set")
    return subset(candidates.value, context.constraint_set(params.required, context.symbols[params.variable]))


def _principal_coverage(assumption, context):
    _, chosen, actual = principal_sine_data(context, assumption.check.equation)
    return subset(actual, chosen)


def _point_formula(assumption, context):
    facts, defined = point_formula_status(context, assumption.check)
    return defined and facts.value is not None


def _lhopital_form(assumption, context):
    form, _ = lhopital_data(context, assumption.check)
    return form


CHECKERS = {
    "nonzero": _predicate,
    "parameter_range": _predicate,
    "log_argument": _predicate,
    "continuity_on_interval": _continuity,
    "domain_predicate": _domain_predicate,
    "candidate_sign": _candidate_predicate,
    "principal_sine_coverage": _principal_coverage,
    "point_formula_defined": _point_formula,
    "lhopital_zero_over_zero": _lhopital_form,
}


def check_assumption(assumption: Assumption, context: Context) -> AssumptionResult:
    rule_id = f"assumption-{assumption.id}"
    try:
        checker = CHECKERS.get(assumption.kind)
        if checker is None:
            raise UnsupportedMath(f"Unsupported assumption kind: {assumption.kind}")
        value = checker(assumption, context)
        status = "satisfied" if value is True else "violated" if value is False else "needs_checking"
        reason = "A required premise has not been established from the remaining facts" if value is None else None
    except (UnsupportedMath, NotImplementedError, ValueError, TypeError) as exc:
        status, reason = "unknown", str(exc)
    return AssumptionResult(
        status=status, reason=reason,
        evidence=Evidence(rule_id=rule_id, outcome=status, summary=f"{assumption.description} Result: {status}."),
    )
