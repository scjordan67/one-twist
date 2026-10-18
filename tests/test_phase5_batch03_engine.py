"""Approved 11-15 matrices through actual checkers and real spawn HTTP."""
import os
from pathlib import Path

import pytest
import sympy as sp
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.parsing import parse_math
from app.engine.classifier import analyze, comparison
from app.engine.context import Context, UnsupportedMath
from app.engine.integrals import two_pole_facts
from app.engine.ivp import ivp_facts
from app.engine.verifier import ProblemEvaluation, evaluate_problem
from app.main import create_app
from app.models.analysis import AnalysisResponse
from app.models.domain import ConclusionResult, MathExpression, FirstOrderIVPSpec, TimeDomain
from app.templates.loader import DEFAULT_DIRECTORY, load_templates, validate_ivp_scopes
from tests.test_phase5_batch03_math import DRAFTS
from tests.test_phase5_batch02_engine import change_for
from tests.test_canonical_arithmetic import ordered_assumptions

STAGING = Path(__file__).resolve().parents[1] / "docs/phase5/batch-03-runtime"
CASES = [(n, case["id"]) for n, draft in sorted(DRAFTS.items()) for case in draft["scenarios"]]


@pytest.fixture(scope="module")
def templates():
    return load_templates(STAGING)


def case_for(number, id):
    return next(item for item in DRAFTS[number]["scenarios"] if item["id"] == id)


def change(template, case):
    if template.id == "integral-endpoint" and case["change_id"]:
        from app.models.domain import Perturbation
        item = next(item for item in DRAFTS[11]["allowed_changes"] if item["id"] == case["change_id"])
        return Perturbation(template_id=template.id, rule_id=item["rule_id"], condition_id=item["condition_id"],
                            type=item["type"], new_value=item["new_value"])
    return change_for(template, case)


def assert_result(result, case):
    report, expected = result.report, case["expected_report"]
    diagnostic = report.model_dump_json()
    assert {id: {label.value for label in item.labels} for id, item in report.step.items()} == {
        id: set(item["labels"]) for id, item in expected["step"].items()
    }, diagnostic
    for dimension in ("method", "conclusion"):
        assert {label.value for label in getattr(report, dimension).labels} == set(expected[dimension]["labels"]), diagnostic
    assert report.comparison.changed == expected["comparison"]["changed"], diagnostic
    assert report.comparison.basis == expected["comparison"]["basis"]
    assert report.first_invalid_step_id == expected["first_invalid_step_id"], diagnostic
    assert report.first_unresolved_step_id == expected["first_unresolved_step_id"], diagnostic
    assert report.problem_well_formedness.value == expected["problem_well_formedness"]
    actual, reference = report.perturbed_outcome, case["reference_outcome"]
    assert actual.status == reference["status"]
    if actual.status in {"numeric_value", "symbolic_formula"}:
        source = reference.get("value", reference.get("formula"))["source"]
        assert actual.value.latex == sp.latex(sp.simplify(parse_math(source, symbols={"t": sp.Symbol("t", real=True)}).doit()))
    if actual.status == "symbolic_formula":
        assert actual.solution_scope == reference["solution_scope"]
        assert actual.variable == reference["variable"] == "t"
        assert actual.time_domain == result.perturbed.problem.computation.time_domain
    if expected["method"].get("remediation"):
        assert report.method.remediation
    assert all(ev.origin == "computed" for dimension in [*report.step.values(), report.method, report.conclusion] for ev in dimension.evidence)
    assert len(result.model_dump_json().encode()) < 65536


@pytest.mark.parametrize("number,id", CASES)
def test_approved_scenario(templates, number, id):
    template = templates[DRAFTS[number]["id"]]
    case = case_for(number, id)
    assert_result(analyze(template, change(template, case)), case)


@pytest.fixture(scope="module")
def client(tmp_path_factory, templates):
    directory = tmp_path_factory.mktemp("batch03-api")
    for path in DEFAULT_DIRECTORY.glob("*.json"):
        (directory/path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    for template in templates.values():
        (directory/(template.id+".json")).write_text(template.model_dump_json(), encoding="utf-8")
    with TestClient(create_app(directory)) as client:
        yield client


@pytest.mark.parametrize("number,id", CASES)
def test_approved_scenario_real_spawn_api(client, templates, number, id):
    template = templates[DRAFTS[number]["id"]]
    case = case_for(number, id)
    perturbation = change(template, case)
    response = client.post("/api/perturbations", json=perturbation.model_dump(mode="json")) if perturbation else client.post(
        "/api/analyze", json={"template_id": template.id})
    assert response.status_code == 200, response.text
    result = AnalysisResponse.model_validate(response.json())
    assert result.execution.status == "success", result.execution
    assert result.execution.worker_pid != os.getpid()
    assert client.app.state.computations.active_count == 0
    assert_result(result, case)


def test_opposing_interior_limits_are_explicit_computed_evidence(templates):
    template = templates[DRAFTS[12]["id"]]
    result = analyze(template, change(template, DRAFTS[12]["scenarios"][1]))
    assert result.report.perturbed_outcome.status == "divergent"
    evidence = next(item for item in result.report.conclusion.evidence if item.rule_id == "split-interior-pole")
    assert "-oo" in evidence.summary and "no principal value" in evidence.summary


@pytest.mark.parametrize("source", ["1/(x*x)", "1/((x-1/2)*(x+1/2))", "sin(x)/x"])
def test_interior_splitting_is_not_a_general_rational_scanner(templates, source):
    template = templates[DRAFTS[12]["id"]].model_copy(deep=True)
    template.original_problem.computation.integrand.source = source
    result = evaluate_problem(Context(template.original_problem))
    assert result.result.status == "unknown"


def test_primitive_and_coefficient_authoring_are_actually_checked(templates):
    template = templates[DRAFTS[12]["id"]].model_copy(deep=True)
    template.verification_rules[0].parameters.primitive.source = "x"
    assert {item.value for item in analyze(template).report.step["primitive-on-components"].labels} == {"Invalid Step"}
    template = templates[DRAFTS[13]["id"]].model_copy(deep=True)
    template.verification_rules[1].parameters.coefficient_values["alpha"].source = "1/a"
    assert {item.value for item in analyze(template).report.step["solve-distinct-coefficients"].labels} == {"Invalid Step"}


def test_rank_and_zero_state_under_adverse_assumption_order(templates, ordered_assumptions):
    for number in (13, 14, 15):
        template = templates[DRAFTS[number]["id"]]
        case = DRAFTS[number]["scenarios"][1]
        assert_result(analyze(template, change(template, case)), case)


def test_zero_pole_raw_domain_under_adverse_assumption_order(templates, ordered_assumptions):
    from app.engine.perturbation import construct_problem
    template = templates[DRAFTS[12]["id"]]
    perturbed = construct_problem(template, change(template, DRAFTS[12]["scenarios"][1]))
    context = Context(perturbed.problem)
    primitive = template.verification_rules[0].parameters.primitive
    raw = context.raw(primitive)
    source_tree = sp.srepr(raw)
    assert sp.Mul(-1, 0, evaluate=False) in raw.args[0].args[0].args
    assert context.domain(primitive, context.symbols["x"]) == sp.S.Reals-sp.FiniteSet(0)
    assert sp.srepr(context.raw(primitive)) == source_tree


@pytest.mark.parametrize("source,expected", [
    ("log(x-c)-log(x-c)", sp.Interval.open(0, sp.oo)),
    ("0*log(x-c)", sp.Interval.open(0, sp.oo)),
    ("(x-c)/(x-c)", sp.S.Reals-sp.FiniteSet(0)),
    ("sqrt(x-c)*sqrt(x-c)", sp.Interval(0, sp.oo)),
])
def test_normalized_domain_queries_retain_every_source_node(templates, ordered_assumptions, source, expected):
    from app.engine.perturbation import construct_problem
    template = templates[DRAFTS[12]["id"]]
    context = Context(construct_problem(template, change(template, DRAFTS[12]["scenarios"][1])).problem)
    expression = MathExpression(source=source, latex=source)
    before = sp.srepr(context.raw(expression))
    assert context.domain(expression, context.symbols["x"]) == expected
    assert sp.srepr(context.raw(expression)) == before


def test_closed_definedness_retains_intermediate_restrictions(templates, ordered_assumptions):
    from app.engine.perturbation import construct_problem
    template = templates[DRAFTS[12]["id"]]
    context = Context(construct_problem(template, change(template, DRAFTS[12]["scenarios"][1])).problem)
    assert context.definedness(MathExpression(source="log(abs(1-c))-log(abs(-1-c))", latex="test")) is True
    assert context.definedness(MathExpression(source="log(c)-log(c)", latex="test")) is False


@pytest.mark.parametrize("number", [14, 15])
def test_actual_rhs_family_is_not_an_authored_label(templates, number):
    template = templates[DRAFTS[number]["id"]].model_copy(deep=True)
    template.original_problem.computation.rhs.source = "y+1"
    with pytest.raises(UnsupportedMath, match="Actual RHS"):
        ivp_facts(Context(template.original_problem))
    assert analyze(template).report.perturbed_outcome.status == "unknown"


def test_reference_repair_requires_a_verified_candidate(templates):
    template = templates[DRAFTS[15]["id"]].model_copy(deep=True)
    template.original_problem.computation.candidate_solutions[0].source = "(t+a)**2"
    report = analyze(template, change(template, DRAFTS[15]["scenarios"][1])).report
    assert report.perturbed_outcome.status == "unknown"
    assert {item.value for item in report.method.labels} == {"Invalid Step"}


def test_no_general_ode_solver_or_authored_failure_evidence(templates, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("No general ODE solver is authorized")
    monkeypatch.setattr(sp, "dsolve", forbidden)
    for number in (14, 15):
        template = templates[DRAFTS[number]["id"]].model_copy(deep=True)
        case = DRAFTS[number]["scenarios"][1]
        before = analyze(template, change(template, case)).model_dump(mode="json")
        template.expected_failure_mechanisms = ["POISON"]
        template.explanation_fragments = []
        assert analyze(template, change(template, case)).model_dump(mode="json") == before


@pytest.mark.parametrize("field,source", [("rhs", "u"), ("initial_value", "t"), ("initial_time", "y")])
def test_ivp_loader_rejects_cross_scope_symbols(templates, field, source):
    template = templates[DRAFTS[15]["id"]].model_copy(deep=True)
    getattr(template.original_problem.computation, field).source = source
    with pytest.raises(ValueError):
        validate_ivp_scopes(template)


def test_ivp_loader_rejects_state_dependent_candidate(templates):
    template = templates[DRAFTS[15]["id"]].model_copy(deep=True)
    template.original_problem.computation.candidate_solutions[0].source = "y"
    with pytest.raises(ValueError):
        validate_ivp_scopes(template)


def test_zero_sqrt_data_does_not_acquire_a_uniqueness_result(templates):
    template = templates[DRAFTS[15]["id"]].model_copy(deep=True)
    spec = template.original_problem.computation
    spec.initial_value.source = "0"
    spec.solution_scope = "unique_solution"
    assert evaluate_problem(Context(template.original_problem)).result.status == "unknown"


@pytest.mark.parametrize("domain", [
    {"lower": None, "left_closed": True},
    {"upper": None, "right_closed": True},
])
def test_unbounded_time_domain_cannot_be_closed(domain):
    with pytest.raises(ValidationError):
        TimeDomain.model_validate(domain)


def test_symbolic_result_requires_exclusive_scope_and_domain(templates):
    result = analyze(templates[DRAFTS[14]["id"]]).report.original_outcome.model_dump(mode="json")
    for key in ("solution_scope", "variable", "time_domain"):
        broken = dict(result)
        broken[key] = None
        with pytest.raises(ValidationError):
            ConclusionResult.model_validate(broken)
    result["status"] = "numeric_value"
    with pytest.raises(ValidationError):
        ConclusionResult.model_validate(result)
