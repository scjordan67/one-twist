"""Approved 06-10 scenarios through finite proofs and actual spawn/API calls."""
import os
from pathlib import Path

import pytest
import sympy as sp
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.isolation import ComputationExecutor
from app.core.parsing import MathSyntaxError, parse_math
from app.engine.classifier import analyze, comparison
from app.engine.context import Context, UnsupportedMath
from app.engine.verifier import ProblemEvaluation, principal_sine_data
from app.main import create_app
from app.models.analysis import AnalysisResponse
from app.models.domain import ConclusionResult, MathExpression, Perturbation, Template
from app.templates.loader import DEFAULT_DIRECTORY, load_templates
from tests.test_phase5_batch02_math import DRAFTS
from tests.test_canonical_arithmetic import ordered_assumptions
from tests.isolation_workers import ordered_assumptions_worker

STAGING = Path(__file__).resolve().parents[1] / "docs/phase5/batch-02-runtime"
CASES = [(number, case["id"]) for number, draft in sorted(DRAFTS.items()) for case in draft["scenarios"]]


@pytest.fixture(scope="module")
def templates():
    return load_templates(STAGING)


def change_for(template, case):
    if case["change_id"] is None:
        return None
    rule = next(item for item in template.allowed_perturbations if item.id == case["change_id"])
    return Perturbation(template_id=template.id, rule_id=rule.id, condition_id=rule.condition_id,
                        type=rule.type, new_value=rule.allowed_values[0])


def assert_report(result, case):
    report, expected = result.report, case["expected_report"]
    diagnostic = report.model_dump_json()
    assert {id: {label.value for label in item.labels} for id, item in report.step.items()} == {
        id: set(item["labels"]) for id, item in expected["step"].items()
    }, diagnostic
    assert {item.value for item in report.method.labels} == set(expected["method"]["labels"]), diagnostic
    assert {item.value for item in report.conclusion.labels} == set(expected["conclusion"]["labels"]), diagnostic
    assert report.comparison.changed == expected["comparison"]["changed"], diagnostic
    assert report.comparison.basis == expected["comparison"]["basis"]
    assert report.first_invalid_step_id == expected["first_invalid_step_id"]
    assert report.first_unresolved_step_id == expected["first_unresolved_step_id"]
    assert report.problem_well_formedness.value == expected["problem_well_formedness"]
    actual, reference = report.perturbed_outcome, case["reference_outcome"]
    assert actual.status == reference["status"]
    if actual.status == "classification":
        assert actual.classification == reference["classification"]
    elif actual.status == "numeric_value":
        assert actual.value.latex == sp.latex(sp.simplify(parse_math(reference["value"]["source"])))
    elif actual.status == "solution_set":
        assert actual.completeness == "complete"
        assert actual.value.latex == sp.latex(sp.FiniteSet(*(sp.simplify(parse_math(item["source"])) for item in reference["values"])))
    if expected["method"]["remediation"]:
        assert report.method.remediation
    assert all(evidence.origin == "computed" for dimension in [*report.step.values(), report.method, report.conclusion] for evidence in dimension.evidence)


@pytest.mark.parametrize("number,case_id", CASES)
def test_approved_scenario_through_actual_checkers(templates, number, case_id):
    draft = DRAFTS[number]
    case = next(item for item in draft["scenarios"] if item["id"] == case_id)
    template = templates[draft["id"]]
    assert_report(analyze(template, change_for(template, case)), case)


@pytest.fixture(scope="module")
def client(tmp_path_factory, templates):
    directory = tmp_path_factory.mktemp("batch02-api")
    for path in DEFAULT_DIRECTORY.glob("*.json"):
        (directory / path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    for template in templates.values():
        (directory / f"{template.id}.json").write_text(template.model_dump_json(), encoding="utf-8")
    with TestClient(create_app(directory)) as client:
        yield client


@pytest.mark.parametrize("number,case_id", CASES)
def test_approved_scenario_through_real_spawn_api(client, templates, number, case_id):
    draft = DRAFTS[number]
    case = next(item for item in draft["scenarios"] if item["id"] == case_id)
    template = templates[draft["id"]]
    change = change_for(template, case)
    response = client.post("/api/perturbations", json=change.model_dump(mode="json")) if change else client.post(
        "/api/analyze", json={"template_id": template.id})
    assert response.status_code == 200, response.text
    result = AnalysisResponse.model_validate(response.json())
    assert result.execution.status == "success", result.execution
    assert result.execution.worker_pid != os.getpid()
    assert client.app.state.computations.active_count == 0
    assert_report(result, case)


def test_sine_checker_verifies_actual_family_and_closed_argument(templates):
    template = templates["sine-principal-branch"].model_copy(deep=True)
    context = Context(template.original_problem)
    spec = template.original_problem.computation
    spec.left.source = "cos(x)"
    with pytest.raises(UnsupportedMath, match="actual equation"):
        principal_sine_data(context, spec)
    spec.left.source = "sin(x)"
    spec.right.source = "x"
    with pytest.raises(UnsupportedMath, match="closed real constant"):
        principal_sine_data(context, spec)


def test_a_punctured_identity_cannot_claim_the_excluded_point(templates):
    template = templates["derivative-cusp"].model_copy(deep=True)
    case = DRAFTS[8]["scenarios"][1]
    template.correct_steps[0].domain_constraints = []
    report = analyze(template, change_for(template, case)).report
    assert {item.value for item in report.step["punctured-derivative"].labels} == {"Unknown"}
    assert {item.value for item in report.step["substitute-at-zero"].labels} == {"Invalid Step"}
    assert report.first_invalid_step_id is None
    assert report.first_unresolved_step_id == "punctured-derivative"


def test_wrong_derivative_formula_is_computed_not_trusted(templates):
    template = templates["derivative-cusp"].model_copy(deep=True)
    template.verification_rules[0].parameters.claimed_derivative.source = "0"
    report = analyze(template).report
    assert {item.value for item in report.step["punctured-derivative"].labels} == {"Invalid Step"}


@pytest.mark.parametrize("id,source", [
    ("derivative-cusp", "sqrt(x*x+t*t+sin(x))"),
    ("stationary-second-derivative", "x**4"),
])
def test_unsupported_function_families_are_unknown(templates, id, source):
    template = templates[id].model_copy(deep=True)
    template.original_problem.computation.expression.source = source
    report = analyze(template).report
    assert report.perturbed_outcome.status == "unknown"
    assert report.perturbed_outcome.reason_if_unknown


def test_lhopital_absent_premise_does_not_invalidate_a_coincidentally_equal_limit(templates):
    template = templates["lhopital-form"].model_copy(deep=True)
    template.original_problem.computation.expression.source = "(x+1)/(x+1)"
    for params in [template.verification_rules[0].parameters, template.verification_rules[1].parameters,
                   template.assumptions[0].check]:
        params.numerator.source = params.denominator.source = "x+1"
    report = analyze(template).report
    assert report.assumptions["indeterminate-form"].status == "violated"
    assert {item.value for item in report.step["replace-quotient-limit"].labels} == {"Needs Checking"}
    assert report.perturbed_outcome.value.latex == "1"


def test_declared_limit_components_must_match_actual_expression(templates):
    template = templates["lhopital-form"].model_copy(deep=True)
    template.verification_rules[1].parameters.numerator.source = "x+2"
    report = analyze(template).report
    assert {item.value for item in report.step["replace-quotient-limit"].labels} == {"Unknown"}


def test_classification_comparison_uses_typed_value_and_ignores_latex():
    def outcome(classification, latex):
        return ProblemEvaluation(ConclusionResult(status="classification", classification=classification,
                                                  value=MathExpression(latex=latex)))
    original = outcome("local_minimum", "display A")
    assert comparison(original, outcome("local_minimum", "display B")).changed is False
    assert comparison(original, outcome("stationary_non_extremum", "display A")).changed is True


@pytest.mark.parametrize("id,edit", [
    ("derivative-cusp", lambda data: data["original_problem"]["computation"].update(variable="missing")),
    ("derivative-cusp", lambda data: data["original_problem"]["computation"].update(order=2)),
    ("stationary-second-derivative", lambda data: data["original_problem"]["computation"].update(kind="generic_proof")),
    ("lhopital-form", lambda data: data["verification_rules"][1]["parameters"].update(required_form="anything")),
    ("sine-principal-branch", lambda data: data["verification_rules"][0]["parameters"]["equation"].update(variable="missing")),
])
def test_new_typed_contracts_reject_unknown_scope_orders_and_forms(templates, id, edit):
    data = templates[id].model_dump(mode="json")
    edit(data)
    with pytest.raises(ValidationError):
        Template.model_validate(data)


def test_a_two_sided_limit_requires_both_punctured_sides(templates):
    template = templates["lhopital-form"].model_copy(deep=True)
    from app.models.domain import Predicate
    template.original_problem.domain_constraints = [Predicate(
        left=MathExpression(source="x", latex="x"), relation="ge", right=MathExpression(source="0", latex="0"))]
    result = analyze(template)
    assert result.report.perturbed_outcome.status == "unknown"
    assert "neighborhood" in result.report.perturbed_outcome.reason_if_unknown


@pytest.mark.parametrize("data", [
    {"status": "classification"},
    {"status": "classification", "classification": True},
    {"status": "numeric_value", "value": {"latex": "0"}, "classification": "local_minimum"},
])
def test_typed_classification_payload_cannot_be_missing_or_numeric(data):
    with pytest.raises(ValidationError):
        ConclusionResult.model_validate(data)


@pytest.mark.parametrize("number", range(6, 11))
def test_author_outcomes_are_not_runtime_evidence(templates, number):
    template = templates[DRAFTS[number]["id"]]
    case = DRAFTS[number]["scenarios"][1]
    change = change_for(template, case)
    expected = analyze(template, change)
    poisoned = template.model_copy(deep=True)
    poisoned.expected_failure_mechanisms = ["POISON ALWAYS VALID OR INVALID"]
    poisoned.conclusion.latex = "POISON AUTHOR ANSWER"
    assert analyze(poisoned, change) == expected


@pytest.mark.parametrize("source", ["asin(1/2)", "diff(x)", "limit(x)"])
def test_calculus_operators_are_not_added_to_input_grammar(source):
    with pytest.raises(MathSyntaxError):
        parse_math(source, symbols=["x"])


def test_new_family_timeout_produces_unknown_not_invalid():
    executor = ComputationExecutor(timeout_seconds=0.001)
    with TestClient(create_app(computation_executor=executor)) as client:
        # Exercise the staged candidate at the same boundary, without public test operations.
        template = load_templates(STAGING)["derivative-cusp"]
        client.app.state.templates[template.id] = template
        response = client.post("/api/analyze", json={"template_id": template.id})
        result = AnalysisResponse.model_validate(response.json())
        assert result.execution.status == "timeout"
        assert {item.value for item in result.report.method.labels} == {"Unknown"}
        assert result.report.perturbed_outcome.status == "unknown"
        assert executor.active_count == 0


def test_publication_keeps_the_accepted_staged_mathematics(templates):
    published = load_templates()
    for id, template in templates.items():
        assert published[id].model_dump(exclude={"review"}) == template.model_dump(exclude={"review"})
        assert published[id].review.status == "reviewed"
        assert published[id].review.reviewer == "Claude Code"


@pytest.mark.parametrize("number,case_id", CASES)
def test_new_families_with_adverse_assumption_order(templates, ordered_assumptions, number, case_id):
    draft = DRAFTS[number]
    case = next(item for item in draft["scenarios"] if item["id"] == case_id)
    template = templates[draft["id"]]
    assert_report(analyze(template, change_for(template, case)), case)


@pytest.mark.parametrize("number,case_id", [(8, "cusp"), (10, "baseline")])
def test_new_zero_parameter_families_in_adverse_order_spawn(templates, number, case_id):
    draft = DRAFTS[number]
    case = next(item for item in draft["scenarios"] if item["id"] == case_id)
    template = templates[draft["id"]]
    change = change_for(template, case)
    executor = ComputationExecutor(_worker_target=ordered_assumptions_worker)
    with TestClient(create_app(computation_executor=executor)) as client:
        response = client.post("/api/analyze", json={
            "template_id": template.id, "perturbation": change.model_dump(mode="json") if change else None,
        })
        result = AnalysisResponse.model_validate(response.json())
        assert result.execution.status == "success", result.execution
        assert_report(result, case)
