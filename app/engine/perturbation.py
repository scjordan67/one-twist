"""Construct exactly one declared condition change without symbolic computation."""

from app.models.analysis import PerturbedProblem
from app.models.domain import AssumptionState, Perturbation, Template


class InvalidPerturbation(ValueError):
    pass


def construct_problem(template: Template, perturbation: Perturbation | None = None) -> PerturbedProblem:
    problem = template.original_problem.model_copy(deep=True)
    problem.well_formedness = None
    assumptions = [item.model_copy(deep=True) for item in template.assumptions]
    result = PerturbedProblem(template_id=template.id, problem=problem, assumptions=assumptions)
    if perturbation is None:
        return result
    if perturbation.template_id != template.id:
        raise InvalidPerturbation("Perturbation template_id does not match the request")
    rule = next((item for item in template.allowed_perturbations if item.id == perturbation.rule_id), None)
    if rule is None or (rule.condition_id, rule.type) != (perturbation.condition_id, perturbation.type):
        raise InvalidPerturbation("Change must match a declared rule, condition_id and type")
    condition = next(item for item in problem.conditions if item.id == rule.condition_id)
    if rule.type == "domain":
        choice = next((item for item in rule.domain_choices if item.id == perturbation.choice_id), None)
        if choice is None or condition.domain_binding is None:
            raise InvalidPerturbation("Domain change must select a declared choice on its bound condition")
        condition.domain_binding.current = choice.domain.model_copy(deep=True)
        problem.variables[condition.domain_binding.variable] = choice.domain.number_system
        for assumption in assumptions:
            if condition.id in assumption.condition_ids:
                assumption.state = AssumptionState.UNCHECKED
    elif rule.type == "remove_assumption":
        if rule.assumption_id is None or perturbation.new_value is not None:
            raise InvalidPerturbation("Assumption removal requires a declared assumption and no new value")
        assumption = next(item for item in assumptions if item.id == rule.assumption_id)
        if rule.condition_id not in assumption.condition_ids:
            raise InvalidPerturbation("Removal must be bound to the assumption's condition")
        assumption.state = AssumptionState.PERTURBED_REMOVED
    else:
        if rule.type not in {"parameter_value", "parameter_sign", "parameter_zero", "interval_endpoint", "degenerate_value"}:
            raise InvalidPerturbation("This perturbation type is not supported in Phase 2")
        if condition.parameter_name is None or condition.predicate is None:
            raise InvalidPerturbation("Condition has no parameter binding")
        source = perturbation.new_value.source if perturbation.new_value else None
        value = next((item for item in rule.allowed_values if item.source is not None and item.source == source), None)
        if value is None:
            raise InvalidPerturbation("Value must be one of the template's exact declared source strings")
        # All content comes from the server's canonical template, including LaTeX.
        parameter = next(item for item in problem.parameters if item.name == condition.parameter_name)
        parameter.value = value.model_copy(deep=True)
        condition.predicate.right = value.model_copy(deep=True)
        for assumption in assumptions:
            if condition.id in assumption.condition_ids:
                assumption.state = AssumptionState.UNCHECKED
        perturbation = perturbation.model_copy(update={"new_value": value.model_copy(deep=True)})
    result.perturbation = perturbation
    return result
