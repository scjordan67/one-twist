"""Approved first-batch mathematics through actual checkers and isolated HTTP."""
import copy
import json
import os
from pathlib import Path

import pytest
import sympy as sp
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.parsing import parse_math
from app.engine.classifier import analyze
from app.engine.context import Context, UnsupportedMath
from app.engine.perturbation import construct_problem
from app.main import create_app
from app.models.domain import Perturbation, Problem, Template
from app.templates.loader import DEFAULT_DIRECTORY, load_templates
from tests.test_phase5_batch01_math import DRAFTS, CASES

STAGING = Path(__file__).resolve().parents[1] / "docs/phase5/batch-01-runtime"


@pytest.fixture(scope="module")
def templates():
    return load_templates(STAGING)


def change_for(template, draft, case):
    if case["change_id"] is None:
        return None
    if draft["matrix_number"] == 1:
        value = case["parameter_values"]["a"]
        rule = next(rule for rule in template.allowed_perturbations if any(item.source == value for item in rule.allowed_values))
        new_value = next(item for item in rule.allowed_values if item.source == value)
        return Perturbation(template_id=template.id, rule_id=rule.id, condition_id=rule.condition_id, type=rule.type, new_value=new_value)
    rule = next(rule for rule in template.allowed_perturbations if rule.id == case["change_id"])
    return Perturbation(template_id=template.id, rule_id=rule.id, condition_id=rule.condition_id, type=rule.type,
                        choice_id=case["domain_choice_id"], new_value=rule.allowed_values[0] if rule.allowed_values else None)


def assert_report(result, draft, case):
    report, expected = result.report, case["expected_report"]
    assert {id: {label.value for label in value.labels} for id, value in report.step.items()} == {id: set(value["labels"]) for id, value in expected["step"].items()}
    assert {label.value for label in report.method.labels} == set(expected["method"]["labels"])
    assert {label.value for label in report.conclusion.labels} == set(expected["conclusion"]["labels"]), report.model_dump_json()
    assert report.first_invalid_step_id == expected["first_invalid_step_id"]
    assert report.first_unresolved_step_id == expected["first_unresolved_step_id"]
    assert report.comparison.changed == expected["comparison"]["changed"]
    assert report.comparison.basis == expected["comparison"]["basis"]
    assert report.problem_well_formedness.value == expected["problem_well_formedness"]
    reference = case["reference_outcome"]
    if reference["status"] == "solution_set":
        value = sp.FiniteSet(*(sp.simplify(parse_math(item["source"])) for item in reference["values"]))
        assert report.perturbed_outcome.completeness == "complete"
    else:
        value = sp.simplify(parse_math(reference["value"]["source"]))
    # Exact display may retain log(4) or expand it to 2*log(2); neither
    # presentation is an independent mathematical difference.
    displays = {sp.latex(value)}
    if reference["status"] == "numeric_value":
        displays.add(sp.latex(sp.expand_log(value)))
    assert report.perturbed_outcome.value.latex in displays
    if expected["method"]["remediation"]:
        assert report.method.remediation
    assert all(ev.origin == "computed" for dimension in [*report.step.values(), report.method, report.conclusion] for ev in dimension.evidence)


@pytest.mark.parametrize("number,case_id", CASES)
def test_approved_scenario_through_real_checkers(templates, number, case_id):
    draft = DRAFTS[number]
    template = templates[draft["id"]]
    case = next(item for item in draft["scenarios"] if item["id"] == case_id)
    result = analyze(template, change_for(template, draft, case))
    assert_report(result, draft, case)
    if number == 3 and case_id == "extraneous-root":
        assert result.report.assumptions["rhs-nonnegative"].status == "violated"
    if number in (2, 4) and case_id == "expanded":
        assert next(iter(result.report.assumptions.values())).status == "violated"


@pytest.fixture(scope="module")
def client(tmp_path_factory, templates):
    directory = tmp_path_factory.mktemp("batch01-api")
    for path in DEFAULT_DIRECTORY.glob("*.json"):
        (directory / path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    for template in templates.values():
        (directory / f"{template.id}.json").write_text(template.model_dump_json(), encoding="utf-8")
    with TestClient(create_app(directory)) as client:
        yield client


@pytest.mark.parametrize("number,case_id", CASES)
def test_approved_scenario_through_real_spawn_api(client, templates, number, case_id):
    from app.models.analysis import AnalysisResponse
    draft = DRAFTS[number]
    template = templates[draft["id"]]
    case = next(item for item in draft["scenarios"] if item["id"] == case_id)
    change = change_for(template, draft, case)
    body = {"template_id": template.id}
    if change is not None:
        body["perturbation"] = change.model_dump(mode="json")
    response = client.post("/api/analyze", json=body)
    assert response.status_code == 200, response.text
    result = AnalysisResponse.model_validate(response.json())
    assert result.execution.status == "success", result.execution
    assert result.execution.worker_pid != os.getpid()
    assert client.app.state.computations.active_count == 0
    assert_report(result, draft, case)


def test_domain_changes_really_widen_the_problem_and_keep_step_restrictions(templates, client):
    for number in (2, 4):
        draft, template = DRAFTS[number], templates[DRAFTS[number]["id"]]
        case = next(item for item in draft["scenarios"] if item["id"] == "expanded")
        change = change_for(template, draft, case)
        before = template.model_dump_json()
        changed = construct_problem(template, change)
        assert template.original_problem.domain_constraints == changed.problem.domain_constraints == []
        assert changed.problem.conditions[-1].domain_binding.current.constraints == []
        assert template.correct_steps[0].domain_constraints
        assert template.model_dump_json() == before
        assert sum(a != b for a, b in zip(template.original_problem.conditions, changed.problem.conditions)) == 1
        response = client.post("/api/perturbations", json=change.model_dump(mode="json"))
        assert response.status_code == 200
        assert response.json()["report"]["comparison"]["changed"] is True


@pytest.mark.parametrize("body_change", [
    {"choice_id": "not-offered"}, {"choice_id": None}, {"new_value": {"source": "2", "latex": "2"}},
    {"condition_id": "not-bound"}, {"domain": {"number_system": "complex", "constraints": []}},
])
def test_domain_payloads_cannot_override_or_bypass_offered_choices(client, templates, body_change):
    draft, template = DRAFTS[2], templates[DRAFTS[2]["id"]]
    case = next(item for item in draft["scenarios"] if item["id"] == "expanded")
    body = change_for(template, draft, case).model_dump(mode="json") | body_change
    assert client.post("/api/perturbations", json=body).status_code == 422
    assert client.app.state.computations.active_count == 0


@pytest.mark.parametrize("source", [
    "log(-1)-log(-1)", "sqrt(-1)*sqrt(-1)", "0*(1/0)", "log(0)-log(0)",
])
def test_cancelled_bad_intermediates_are_not_valid_real_scalars(templates, source):
    template = templates["real-log-product"].model_copy(deep=True)
    expression = template.original_problem.computation.expression
    expression.source = source
    context = Context(template.original_problem)
    assert context.definedness(expression) is False
    # The current problem itself now contains this expression, unlike the
    # approved negative-t case whose original log(t*t) stays well formed.
    result = analyze(template)
    assert result.report.perturbed_outcome.status == "undefined"
    assert result.report.problem_well_formedness.value == "Undefined"


def test_zero_power_zero_is_unknown_rather_than_an_assumed_convention(templates):
    template = templates["real-log-product"].model_copy(deep=True)
    template.original_problem.computation.expression.source = "0**0"
    assert analyze(template).report.perturbed_outcome.status == "unknown"


def test_real_parameter_construction_cannot_hide_complex_intermediates(templates):
    template = templates["real-log-product"].model_copy(deep=True)
    template.original_problem.parameters[0].value.source = "log(-1)-log(-1)"
    # It simplifies to a real zero, but it is not a valid real parameter
    # construction. A worker must not erase the invalid intermediates.
    with pytest.raises(UnsupportedMath, match="Parameter construction"):
        Context(template.original_problem)


@pytest.mark.parametrize("edit,message", [
    (lambda data: data["original_problem"]["domain_constraints"].extend(data["original_problem"]["conditions"][0]["domain_binding"]["current"]["constraints"]), "fixed and mutable"),
    (lambda data: data["original_problem"]["variables"].update(x="complex"), "number system"),
    (lambda data: data["assumptions"][0]["check"].update(variable="missing"), "Unknown reference"),
    (lambda data: data["allowed_perturbations"][0]["domain_choices"].append(copy.deepcopy(data["allowed_perturbations"][0]["domain_choices"][0])), "Duplicate"),
    (lambda data: data["assumptions"][0]["check"].update(operation="candidate_predicate"), "validation"),
])
def test_domain_and_scope_contracts_reject_invalid_content(templates, edit, message):
    data = templates["cancelled-factor-domain"].model_dump(mode="json")
    edit(data)
    with pytest.raises(ValidationError):
        Template.model_validate(data)


def test_violated_domain_premise_does_not_by_itself_make_a_verified_step_invalid(templates):
    template = templates["inverse-square-domain"].model_copy(deep=True)
    template.original_problem.conditions[-1].domain_binding.current.constraints = []
    template.correct_steps = template.correct_steps[:1]
    template.correct_steps[0].domain_constraints = []
    template.verification_rules = template.verification_rules[:1]
    rule = template.verification_rules[0]
    rule.parameters.after = rule.parameters.before.model_copy(deep=True)
    template.explanation_fragments = []
    result = analyze(template)
    assert result.report.assumptions["principal-branch-covers-domain"].status == "violated"
    assert {item.value for item in result.report.step["apply-principal-inverse"].labels} == {"Valid"}


def test_author_expected_answers_are_not_runtime_evidence(templates):
    for template in templates.values():
        baseline = analyze(template)
        poisoned = template.model_copy(deep=True)
        poisoned.expected_failure_mechanisms = ["POISONED: ALWAYS INVALID"]
        poisoned.conclusion.latex = "POISONED ANSWER"
        assert analyze(poisoned) == baseline


def test_published_templates_match_the_staged_accepted_mathematics(templates):
    published = load_templates()
    for id, staged in templates.items():
        assert published[id].model_dump(exclude={"review"}) == staged.model_dump(exclude={"review"})
        assert published[id].review.status == "reviewed"
        assert published[id].review.reviewer == "Claude Code"


def test_mode_b_grades_domain_choices_using_computed_goals(client, templates):
    template = templates["cancelled-factor-domain"]
    challenge = client.app.state.challenges.challenges["practice-003"]
    original_id = challenge.template_id
    challenge.template_id = template.id  # Synthetic binding, never stored/published.
    try:
        for rule, expected in zip(template.allowed_perturbations, ("Correct", "Incorrect")):
            response = client.post("/api/challenges/check", json={
                "challenge_id": challenge.id, "mode": "B",
                "perturbation": {"template_id": template.id, "rule_id": rule.id, "condition_id": rule.condition_id,
                                 "type": "domain", "choice_id": rule.domain_choices[0].id, "new_value": None},
            })
            assert response.status_code == 200
            data = response.json()
            assert data["analysis"]["execution"]["status"] == "success"
            assert data["grade"] == expected
    finally:
        challenge.template_id = original_id


@pytest.mark.parametrize("attempt", range(8))
def test_radical_control_comparison_is_stable_across_fresh_workers(client, templates, attempt, monkeypatch):
    monkeypatch.setenv("PYTHONHASHSEED", str(attempt))
    draft = DRAFTS[3]
    template = templates[draft["id"]]
    case = next(item for item in draft["scenarios"] if item["id"] == "valid-control")
    change = change_for(template, draft, case)
    response = client.post("/api/analyze", json={"template_id": template.id, "perturbation": change.model_dump(mode="json")})
    assert response.status_code == 200
    data = response.json()
    assert data["execution"]["status"] == "success", data["execution"]
    assert data["report"]["comparison"]["changed"] is True, json.dumps({
        "execution": data["execution"],
        "original_outcome": data["report"]["original_outcome"],
        "perturbed_outcome": data["report"]["perturbed_outcome"],
        "comparison": data["report"]["comparison"],
    }, ensure_ascii=False)
