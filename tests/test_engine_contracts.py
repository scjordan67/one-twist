import pytest
from pydantic import ValidationError

from app.engine.perturbation import InvalidPerturbation, construct_problem
from app.models.analysis import AnalysisRequest
from app.models.domain import AssumptionState, Perturbation, Template
from app.templates.loader import load_templates


def change(template, rule_index=0, value_index=0):
    rule = template.allowed_perturbations[rule_index]
    return Perturbation(
        template_id=template.id, rule_id=rule.id, condition_id=rule.condition_id,
        type=rule.type, new_value=rule.allowed_values[value_index].model_copy(deep=True) if rule.allowed_values else None,
    )


@pytest.mark.parametrize("template_id", ["linear-degeneration", "integral-endpoint"])
def test_single_condition_change_is_canonical_and_does_not_mutate_template(template_id):
    template = load_templates()[template_id]
    original = template.model_dump_json()
    perturbation = change(template)
    perturbation.new_value.latex = "untrusted client display"
    result = construct_problem(template, perturbation)
    before, after = template.original_problem, result.problem
    assert len([1 for a, b in zip(before.conditions, after.conditions) if a != b]) == 1
    assert len([1 for a, b in zip(before.parameters, after.parameters) if a != b]) == 1
    assert result.problem.well_formedness is None
    assert result.problem.domain_constraints == before.domain_constraints
    assert result.perturbation.new_value.latex != "untrusted client display"
    assert template.model_dump_json() == original


@pytest.mark.parametrize("field,value", [
    ("template_id", "absent"), ("rule_id", "absent"),
    ("condition_id", "absent"), ("type", "domain"),
    ("new_value", {"source": "__import__('os')", "latex": "0"}),
    ("new_value", {"source": "100", "latex": "0"}), ("new_value", None),
])
def test_unlisted_or_misbound_changes_are_rejected(field, value):
    template = load_templates()["linear-degeneration"]
    data = change(template).model_dump()
    data[field] = value
    with pytest.raises((InvalidPerturbation, ValidationError)):
        construct_problem(template, Perturbation.model_validate(data))


def test_removing_an_assumption_is_not_asserting_it_false(template_data):
    template_data["allowed_perturbations"].append({
        "id": "remove-nonzero", "condition_id": "parameter-a", "type": "remove_assumption",
        "assumption_id": "a-nonzero", "description": "Remove the asserted premise",
    })
    template = Template.model_validate(template_data)
    result = construct_problem(template, change(template, 2))
    assert result.assumptions[0].state == AssumptionState.PERTURBED_REMOVED
    assert result.assumptions[0].state != AssumptionState.PERTURBED_FALSE
    assert result.problem.parameters == template.original_problem.parameters


def test_parameter_binding_and_computation_variable_references_are_validated(template_data):
    template_data["original_problem"]["conditions"][0]["parameter_name"] = "missing"
    with pytest.raises(ValidationError, match="Unknown reference"):
        Template.model_validate(template_data)
    template_data["original_problem"]["conditions"][0]["parameter_name"] = "a"
    template_data["original_problem"]["computation"]["variable"] = "missing"
    with pytest.raises(ValidationError, match="computation variable"):
        Template.model_validate(template_data)


def test_parameter_binding_must_agree_with_original_value(template_data):
    template_data["original_problem"]["conditions"][0]["predicate"]["right"]["source"] = "0"
    with pytest.raises(ValidationError, match="bind its declared parameter"):
        Template.model_validate(template_data)


def test_computation_and_rule_specs_are_finite_unions(template_data):
    template_data["verification_rules"][0]["parameters"]["operation"] = "run_code"
    with pytest.raises(ValidationError, match="union_tag_invalid"):
        Template.model_validate(template_data)


def test_analysis_request_rejects_client_verdicts():
    with pytest.raises(ValidationError, match="Extra inputs"):
        AnalysisRequest(template_id="linear-degeneration", report={"labels": ["Valid"]})
