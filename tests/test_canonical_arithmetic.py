"""The retained input tree is not SymPy's canonical computation tree."""
import importlib

import pytest
import sympy as sp
from fastapi.testclient import TestClient
from sympy.core.cache import clear_cache
from sympy.core.facts import InconsistentAssumptions

from app.core.isolation import ComputationExecutor
from app.engine.classifier import analyze
from app.engine.context import Context
from app.main import create_app
from app.models.analysis import AnalysisResponse
from app.models.domain import MathExpression
from app.templates.loader import load_templates
from tests.isolation_workers import order_assumption_facts, ordered_assumptions_worker
from tests.test_phase5_batch01_engine import assert_report, change_for
from tests.test_phase5_batch01_math import DRAFTS


@pytest.fixture
def ordered_assumptions(monkeypatch):
    assumptions = importlib.import_module("sympy.core.assumptions")
    monkeypatch.setattr(assumptions, "shuffle", order_assumption_facts)
    clear_cache()
    yield
    clear_cache()


def test_canonical_computation_avoids_raw_zero_product_conflict(ordered_assumptions):
    template = load_templates()["squared-candidates-sign"]
    context = Context(template.original_problem)
    expression = template.original_problem.computation.right
    raw = context.raw(expression)
    source_tree = sp.srepr(raw)
    assert sp.Mul(-1, 0, evaluate=False) in raw.args
    # Characterize the locked SymPy version with the real failing operation.
    # No fake solveset result or comparison value is injected.
    with pytest.raises(InconsistentAssumptions):
        sp.simplify(raw)
    assert context.expr(expression) == context.symbols["x"]
    assert sp.srepr(context.raw(expression)) == source_tree


@pytest.mark.parametrize("source,expected_domain,expected_value", [
    ("x/x", sp.S.Reals - sp.FiniteSet(0), 1),
    ("x*x/x", sp.S.Reals - sp.FiniteSet(0), "x"),
    ("log(x)-log(x)", sp.Interval.open(0, sp.oo), 0),
    ("sqrt(x)*sqrt(x)", sp.Interval(0, sp.oo), "x"),
])
def test_computation_normalization_preserves_source_domain(ordered_assumptions, source, expected_domain, expected_value):
    context = Context(load_templates()["squared-candidates-sign"].original_problem)
    expression = MathExpression(source=source, latex=source)
    variable = context.symbols["x"]
    before = sp.srepr(context.raw(expression))
    assert context.expr(expression) == (variable if expected_value == "x" else expected_value)
    assert context.domain(expression, variable) == expected_domain
    assert sp.srepr(context.raw(expression)) == before


@pytest.mark.parametrize("source", ["-0", "0-0", "0*1"])
def test_zero_parameter_arithmetic_is_normalized(ordered_assumptions, source):
    problem = load_templates()["linear-degeneration"].original_problem.model_copy(deep=True)
    problem.parameters[0].value = MathExpression(source=source, latex=source)
    context = Context(problem)
    assert context.values[context.symbols["a"]] == 0
    assert context.expr(MathExpression(source="a*x", latex="ax")) == 0


@pytest.mark.parametrize("case_id", ["baseline", "valid-control", "extraneous-root"])
def test_radical_analysis_with_adverse_assumption_order(ordered_assumptions, case_id):
    draft = DRAFTS[3]
    case = next(item for item in draft["scenarios"] if item["id"] == case_id)
    template = load_templates()[draft["id"]]
    result = analyze(template, change_for(template, draft, case))
    assert result.report.original_outcome.status == "solution_set", result.report.original_outcome
    assert result.report.original_outcome.value.latex == sp.latex(sp.FiniteSet(0, 1))
    assert_report(result, draft, case)


@pytest.mark.parametrize("case_id", ["baseline", "valid-control", "extraneous-root"])
def test_real_spawn_api_with_adverse_assumption_order(case_id):
    draft = DRAFTS[3]
    case = next(item for item in draft["scenarios"] if item["id"] == case_id)
    template = load_templates()[draft["id"]]
    change = change_for(template, draft, case)
    executor = ComputationExecutor(_worker_target=ordered_assumptions_worker)
    with TestClient(create_app(computation_executor=executor)) as client:
        response = client.post("/api/analyze", json={
            "template_id": template.id,
            "perturbation": change.model_dump(mode="json") if change else None,
        })
        assert response.status_code == 200
        result = AnalysisResponse.model_validate(response.json())
        assert result.execution.status == "success", result.execution
        assert result.report.original_outcome.status == "solution_set", result.report.original_outcome
        assert result.report.original_outcome.value.latex == sp.latex(sp.FiniteSet(0, 1))
        assert_report(result, draft, case)
        assert executor.active_count == 0
