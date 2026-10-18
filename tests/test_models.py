import pytest
from pydantic import ValidationError

from app.models import (
    AssumptionState, ConclusionComparison, DimensionResult, Step,
    Template, ValidityLabel, ValidityReport,
)


def test_three_dimensions_are_independent():
    report = ValidityReport(
        step={"divide": DimensionResult(labels={ValidityLabel.VALID})},
        method=DimensionResult(labels={ValidityLabel.VALID}),
        conclusion=DimensionResult(labels={ValidityLabel.CHANGED_CONCLUSION}),
    )
    assert report.step["divide"].labels == {ValidityLabel.VALID}
    assert report.conclusion.labels == {ValidityLabel.CHANGED_CONCLUSION}


def test_unknown_needs_a_specific_reason():
    with pytest.raises(ValidationError, match="reason_if_unknown"):
        DimensionResult(labels={ValidityLabel.UNKNOWN})
    unknown = DimensionResult(labels={ValidityLabel.UNKNOWN}, reason_if_unknown="Unsupported complex branch")
    pending = DimensionResult(labels={ValidityLabel.NEEDS_CHECKING})
    assert unknown.reason_if_unknown and pending.reason_if_unknown is None


def test_inconvenient_requires_author_reviewed_evidence():
    with pytest.raises(ValidationError, match="author-reviewed"):
        DimensionResult(labels={ValidityLabel.INCONVENIENT})
    result = DimensionResult(
        labels={ValidityLabel.VALID, ValidityLabel.INCONVENIENT},
        evidence=[{"rule_id": "author-note", "summary": "An audited pedagogical choice", "origin": "author_reviewed"}],
    )
    assert len(result.labels) == 2


def test_step_rejects_conflicting_verdicts(template_data):
    data = template_data["correct_steps"][0]
    data["verification"] = {"labels": ["Valid", "Invalid Step"]}
    with pytest.raises(ValidationError, match="both Valid and Invalid"):
        Step.model_validate(data)


def test_report_preserves_per_step_verdicts():
    report = ValidityReport(
        step={
            "first": {"labels": ["Valid"]},
            "second": {"labels": ["Unknown"], "reason_if_unknown": "Branch not supported"},
            "third": {"labels": ["Invalid Step"]},
        },
        method={"labels": ["Needs Checking"], "remediation": "Split the parameter cases"},
        conclusion={"labels": ["Unknown"], "reason_if_unknown": "Incomplete solution set"},
        first_invalid_step_id="third", first_unresolved_step_id="second",
    )
    assert report.first_invalid_step_id != report.first_unresolved_step_id
    assert report.method.remediation


@pytest.mark.parametrize("field", ["first_invalid_step_id", "first_unresolved_step_id"])
def test_report_rejects_dangling_verdict_reference(field):
    data = dict(step={}, method={"labels": ["Needs Checking"]}, conclusion={"labels": ["Needs Checking"]})
    data[field] = "absent"
    with pytest.raises(ValidationError, match="must reference"):
        ValidityReport.model_validate(data)


def test_report_rejects_conflicting_single_step():
    with pytest.raises(ValidationError, match="both Valid and Invalid"):
        ValidityReport(
            step={"first": {"labels": ["Valid", "Invalid Step"]}},
            method={"labels": ["Needs Checking"]}, conclusion={"labels": ["Needs Checking"]},
        )


def test_constraints_and_assumption_states_survive_roundtrip(template_data):
    template = Template.model_validate(template_data)
    restored = Template.model_validate_json(template.model_dump_json())
    assert restored.correct_steps[0].domain_constraints[0].relation == "ne"
    assert restored.correct_steps[0].verification is None
    removed = template.assumptions[0].model_copy(update={"state": AssumptionState.PERTURBED_REMOVED})
    assert removed.state != AssumptionState.PERTURBED_FALSE


def test_unknown_conclusion_comparison_is_not_unchanged():
    result = ConclusionComparison(basis="numeric_value", original={"source": "1", "latex": "1"})
    assert result.changed is None


def test_unassessed_problem_is_not_implicitly_well_formed(template_data):
    del template_data["original_problem"]["well_formedness"]
    assert Template.model_validate(template_data).original_problem.well_formedness is None


def test_extra_fields_are_rejected(template_data):
    template_data["pretend_verified"] = True
    with pytest.raises(ValidationError, match="Extra inputs"):
        Template.model_validate(template_data)
