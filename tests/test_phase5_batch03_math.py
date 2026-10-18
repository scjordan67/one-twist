"""Private 11-15 draft mathematics, independently calculated; no new checker."""
import json
from pathlib import Path

import pytest
import sympy as sp
from fastapi.testclient import TestClient
from pydantic import TypeAdapter, ValidationError

from app.core.parsing import parse_math
from app.main import create_app
from app.models.domain import Assumption, ComputationSpec, DimensionResult, Method, Problem, Review, Step
from app.templates.loader import DEFAULT_DIRECTORY, load_templates

DIRECTORY = Path(__file__).resolve().parents[1] / "docs/phase5/batch-03"
DRAFTS = {data["matrix_number"]: data for path in DIRECTORY.glob("*.json")
          if (data := json.loads(path.read_text(encoding="utf-8")))}


def symbols(draft):
    problem = draft["original_problem"]
    return {name: sp.Symbol(name, real=True)
            for name in [*problem["variables"], *(item["name"] for item in problem["parameters"])]}


def arithmetic(draft, source, case):
    names = symbols(draft)
    values = {names[name]: parse_math(value).doit() for name, value in case["parameter_values"].items()}
    # Normalize the computation copy; the review snapshot/source stays intact.
    return sp.simplify(parse_math(source, symbols=names).subs(values).doit())


def assert_numeric(draft, outcome, case, actual):
    assert outcome["status"] == "numeric_value"
    assert sp.simplify(actual-arithmetic(draft, outcome["value"]["source"], case)) == 0


@pytest.mark.parametrize("number", range(11, 16))
def test_private_review_packets_have_valid_snapshots_references_and_one_change(number):
    draft = DRAFTS[number]
    review = Review.model_validate(draft["review"])
    assert review.status == "draft" and review.reviewer is None
    problem = Problem.model_validate(draft["original_problem"])
    assumptions = [Assumption.model_validate(item) for item in draft["assumptions"]]
    methods = [Method.model_validate(item) for item in draft["methods"]]
    steps = [Step.model_validate(item) for item in draft["correct_steps"]]
    assert [item.number for item in steps] == list(range(1, len(steps)+1))
    assumption_ids = {item.id for item in assumptions}
    condition_ids = {item.id for item in problem.conditions}
    method_ids = {item.id for item in methods}
    assert len({item.id for item in steps}) == len(steps)
    assert all(set(item.condition_ids) <= condition_ids for item in assumptions)
    assert all(set(item.assumption_ids) <= assumption_ids for item in methods)
    assert all(item.method_id in method_ids and set(item.assumption_ids) <= assumption_ids for item in steps)
    assert {item["step_id"] for item in draft["planned_checks"]} == {item.id for item in steps}
    changes = {item["id"]: item for item in draft["allowed_changes"]}
    assert len(changes) == len(draft["allowed_changes"])
    baseline = {item.name: item.value.source for item in problem.parameters}
    assert draft["scenarios"][0]["parameter_values"] == baseline
    for case in draft["scenarios"]:
        expected = case["expected_report"]
        for item in [*expected["step"].values(), expected["method"], expected["conclusion"]]:
            DimensionResult.model_validate(item)
        assert set(expected["step"]) == {item.id for item in steps}
        changed = [key for key in baseline if baseline[key] != case["parameter_values"][key]]
        assert len(changed) == (0 if case["change_id"] is None else 1)
        if changed:
            change = changes[case["change_id"]]
            condition = next(item for item in problem.conditions if item.id == change["condition_id"])
            assert condition.parameter_name == changed[0]
            assert change["new_value"]["source"] == case["parameter_values"][changed[0]]

    def sources(node):
        if isinstance(node, dict):
            if node.get("source") is not None and "latex" in node:
                parse_math(node["source"], symbols=symbols(draft))
            for item in node.values():
                sources(item)
        elif isinstance(node, list):
            for item in node:
                sources(item)
    sources(draft)


@pytest.mark.parametrize("case", DRAFTS[11]["scenarios"], ids=lambda item: item["id"])
def test_11_existing_endpoint_values_and_improper_limit(case):
    draft = DRAFTS[11]
    x = symbols(draft)["x"]
    b = arithmetic(draft, "b", case)
    f = 1/(1-x)
    if b == 1:
        z = sp.Symbol("z", positive=True)
        truncated = sp.integrate(f, (x, 0, 1-z))
        assert sp.limit(truncated, z, 0, dir="+") is sp.oo
        assert case["reference_outcome"]["status"] == "divergent"
        assert case["reference_outcome"]["signed_direction"] == "positive"
        assert case["expected_report"]["method"]["labels"] == ["Needs Checking"]
        assert case["expected_report"]["comparison"]["changed"] is True
    else:
        actual = sp.integrate(f, (x, 0, b))
        assert_numeric(draft, case["reference_outcome"], case, actual)
        assert sp.Interval(0, b).is_subset(sp.Interval.open(-sp.oo, 1)) is True
        assert case["expected_report"]["comparison"]["changed"] == (sp.simplify(actual-sp.log(2)).is_zero is False)


@pytest.mark.parametrize("case", DRAFTS[12]["scenarios"], ids=lambda item: item["id"])
def test_12_independent_interior_limits_and_regular_controls(case):
    draft = DRAFTS[12]
    x = symbols(draft)["x"]
    c = arithmetic(draft, "c", case)
    f = 1/(x-c)
    domain = sp.calculus.util.continuous_domain(f, x, sp.S.Reals)
    assert domain == sp.S.Reals - sp.FiniteSet(c)
    # The derivative identity remains true on each separate component.
    h = sp.Symbol("h", positive=True)
    for sign in (-1, 1):
        F = sp.log(sp.Abs(sign*h))
        assert sp.simplify(sign*sp.diff(F, h) - 1/(sign*h)) == 0
    endpoint_expression = sp.log(sp.Abs(1-c))-sp.log(sp.Abs(-1-c))
    if c == 0:
        left_cutoff, right_cutoff = sp.symbols("left_cutoff right_cutoff", positive=True)
        left = sp.integrate(f, (x, -1, -left_cutoff))
        right = sp.integrate(f, (x, right_cutoff, 1))
        left_limit = sp.limit(left, left_cutoff, 0, dir="+")
        right_limit = sp.limit(right, right_cutoff, 0, dir="+")
        assert left_limit is -sp.oo and right_limit is sp.oo
        assert [item["signed_direction"] for item in case["one_sided_pieces"]] == ["negative", "positive"]
        assert case["reference_outcome"]["signed_direction"] is None
        assert case["reference_outcome"]["status"] == "divergent"
        assert_numeric(draft, case["derivation_claim"], case, endpoint_expression)
        assert endpoint_expression == 0  # A valid local scalar calculation, not an integral.
        epsilon = sp.Symbol("epsilon", positive=True)
        symmetric = sp.simplify(left.subs(left_cutoff, epsilon)+right.subs(right_cutoff, epsilon))
        assert sp.limit(symmetric, epsilon, 0, dir="+") == 0
        assert case["symmetric_principal_value"]["is_requested_answer"] is False
        assert case["expected_report"]["first_invalid_step_id"] == "apply-endpoint-formula"
        assert case["expected_report"]["comparison"]["changed"] is True
    else:
        assert sp.Interval(-1, 1).is_subset(domain) is True
        actual = sp.integrate(f, (x, -1, 1))
        assert_numeric(draft, case["reference_outcome"], case, actual)
        assert sp.simplify(actual-endpoint_expression) == 0
        assert case["expected_report"]["comparison"]["changed"] == (sp.simplify(actual+sp.log(3)).is_zero is False)


@pytest.mark.parametrize("case", DRAFTS[13]["scenarios"], ids=lambda item: item["id"])
def test_13_actual_pole_multiplicity_coefficient_rank_and_integral(case):
    draft = DRAFTS[13]
    x = symbols(draft)["x"]
    a = arithmetic(draft, "a", case)
    denominator = x*(x-a)
    f = 1/denominator
    roots = sp.roots(denominator, x)
    assert all(not bool(sp.Interval(2, 3).contains(root)) for root in roots)
    assert sp.Interval(2, 3).is_subset(sp.calculus.util.continuous_domain(f, x, sp.S.Reals)) is True
    actual = sp.integrate(f, (x, 2, 3))
    assert_numeric(draft, case["reference_outcome"], case, actual)
    assert case["expected_report"]["comparison"]["changed"] == (sp.simplify(actual-sp.log(sp.Rational(4, 3))).is_zero is False)
    matrix, target = sp.Matrix([[1, 1], [-a, 0]]), sp.Matrix([0, 1])
    alpha, beta = sp.symbols("alpha beta", real=True)
    coefficient_solutions = sp.linsolve((matrix, target), (alpha, beta))
    if a == 0:
        assert roots == {sp.S.Zero: 2}
        assert matrix.rank() == 1 and matrix.row_join(target).rank() == 2
        assert coefficient_solutions is sp.S.EmptySet
        assert actual == sp.Rational(1, 6)
        repair = case["verified_repair"]
        repaired = (alpha/x + beta/x**2).subs({alpha: 0, beta: 1})
        primitive = arithmetic(draft, repair["primitive"]["source"], case)
        assert sp.simplify(repaired-f) == 0
        assert sp.simplify(sp.diff(primitive, x)-f) == 0
        assert sp.simplify(primitive.subs(x, 3)-primitive.subs(x, 2)) == actual
        assert case["expected_report"]["method"]["labels"] == ["Needs Checking"]
        assert case["expected_report"]["problem_well_formedness"] == "WellFormed"
    else:
        assert all(multiplicity == 1 for multiplicity in roots.values())
        assert coefficient_solutions == sp.FiniteSet((-1/a, 1/a))
        decomposed = -1/(a*x)+1/(a*(x-a))
        assert sp.simplify(decomposed-f) == 0
        endpoint = arithmetic(draft, draft["planned_checks"][-1]["expression"]["source"], case)
        assert sp.simplify(actual-endpoint) == 0


def test_13_parameter_limit_is_finite_but_not_substitution_into_zero_denominator():
    a = sp.Symbol("a", real=True)
    # On a neighborhood of zero, all integration poles remain outside [2,3].
    formula = (sp.log(3-a)-sp.log(3)-sp.log(2-a)+sp.log(2))/a
    assert formula.subs(a, 0) is sp.nan
    assert sp.limit(formula, a, 0) == sp.Rational(1, 6)


@pytest.mark.parametrize("case", DRAFTS[14]["scenarios"], ids=lambda item: item["id"])
def test_14_original_ivp_residual_initial_data_and_zero_case(case):
    draft = DRAFTS[14]
    names = symbols(draft)
    t, y = names["t"], names["y"]
    a = arithmetic(draft, "a", case)
    spec = draft["proposed_computation"]
    assert arithmetic(draft, spec["rhs"]["source"], case) == y
    candidate = arithmetic(draft, spec["candidate_solutions"][0]["source"], case)
    initial = arithmetic(draft, spec["initial_value"]["source"], case)
    assert sp.simplify(sp.diff(candidate, t)-candidate) == 0
    assert candidate.subs(t, 0) == initial == a
    assert sp.calculus.util.continuous_domain(candidate, t, sp.S.Reals) == sp.S.Reals
    assert sp.simplify(candidate-arithmetic(draft, case["reference_outcome"]["formula"]["source"], case)) == 0
    assert case["reference_outcome"]["solution_scope"] == "unique_solution"
    assert sp.exp(t).is_positive is True
    if a == 0:
        assert candidate == 0
        assert sp.log(sp.Abs(initial)).is_finite is False  # Not a real finite value.
        s = sp.Symbol("s", positive=True)
        assert sp.limit(sp.log(s), s, 0, dir="+") is -sp.oo
        assert case["expected_report"]["step"]["verify-original-ivp"]["labels"] == ["Valid"]
        assert case["expected_report"]["first_invalid_step_id"] == "divide-by-state"
    else:
        assert sp.simplify(sp.diff(candidate, t)/candidate) == 1
        assert sp.sign(candidate) == sp.sign(a)
        assert sp.simplify(sp.log(sp.Abs(candidate))-t-sp.log(sp.Abs(a))) == 0
    # Uniqueness is not inferred from finding this one candidate.
    Y = sp.Function("Y")(t)
    identity = sp.diff(sp.exp(-t)*Y, t)-sp.exp(-t)*(sp.diff(Y, t)-Y)
    assert sp.simplify(identity) == 0  # Every solution has constant integrating factor.
    assert case["expected_report"]["comparison"]["changed"] == ((candidate-sp.exp(t)).subs(t, 0) != 0)


@pytest.mark.parametrize("case", DRAFTS[15]["scenarios"], ids=lambda item: item["id"])
def test_15_entire_forward_domain_and_principal_initial_root(case):
    draft = DRAFTS[15]
    names = symbols(draft)
    t, y = names["t"], names["y"]
    a = arithmetic(draft, "a", case)
    spec = draft["proposed_computation"]
    assert arithmetic(draft, spec["rhs"]["source"], case) == 2*sp.sqrt(y)
    assert a*a > 0
    candidate = arithmetic(draft, spec["candidate_solutions"][0]["source"], case)
    h = sp.Symbol("h", nonnegative=True)
    forward = candidate.subs(t, h)
    assert sp.simplify(sp.diff(forward, h)-2*sp.sqrt(forward)) == 0
    assert forward.is_nonnegative is True and forward.subs(h, 0) == a*a
    assert sp.sqrt(a*a) == sp.Abs(a)
    assert sp.simplify(candidate-arithmetic(draft, case["reference_outcome"]["formula"]["source"], case)) == 0
    assert case["reference_outcome"]["solution_scope"] == "verified_witness"
    assert case["expected_report"]["comparison"]["changed"] == (not sp.Poly(candidate-(t+1)**2, t).is_zero)
    claim = arithmetic(draft, case["derivation_claim"]["formula"]["source"], case)
    assert claim.subs(t, 0) == a*a
    if a < 0:
        point = arithmetic(draft, case["counterexample"]["time"]["source"], case)
        lhs = sp.diff(claim, t).subs(t, point)
        rhs = 2*sp.sqrt(claim.subs(t, point))
        assert point == sp.Rational(1, 2) and lhs == -1 and rhs == 1
        assert lhs-rhs == arithmetic(draft, case["counterexample"]["residual"]["source"], case)
        z = sp.Symbol("z", positive=True)
        residual = sp.diff(claim, t)-2*sp.sqrt(claim)
        assert sp.simplify(residual.subs(t, 1-z)) == -4*z
        assert sp.simplify(residual.subs(t, 1+z)) == 0
        assert case["same_ivp_as_baseline"] is True
        assert case["expected_report"]["comparison"]["changed"] is False
        assert case["expected_report"]["first_invalid_step_id"] == "choose-initial-root"
    else:
        assert sp.simplify(sp.diff(claim.subs(t, h), h)-2*sp.sqrt(claim.subs(t, h))) == 0


@pytest.mark.parametrize("number", [14, 15])
def test_proposed_ivp_contracts_have_separate_scopes_and_are_not_runtime_members(number):
    draft = DRAFTS[number]
    spec = draft["proposed_computation"]
    names = symbols(draft)
    assert spec["independent_variable"] != spec["dependent_variable"]
    assert {spec["independent_variable"], spec["dependent_variable"]} <= set(names)
    assert len(spec["candidate_solutions"]) == 1
    assert parse_math(spec["rhs"]["source"], symbols=names).free_symbols <= {names[spec["dependent_variable"]]}
    for candidate in spec["candidate_solutions"]:
        assert parse_math(candidate["source"], symbols=names).free_symbols <= {names["t"], names["a"]}
    domain = spec["time_domain"]
    assert domain["upper"] is None and domain["right_closed"] is False
    if number == 14:
        assert domain["lower"] is None and domain["left_closed"] is False
        assert spec["state_domain"]["constraints"] == []
        assert draft["original_problem"]["domain_constraints"] == []
    else:
        assert domain["lower"]["source"] == "0" and domain["left_closed"] is True
        assert spec["question"] == "solution" and spec["solution_scope"] == "verified_witness"
        assert spec["state_domain"]["constraints"][0]["left"]["source"] == "y"
    with pytest.raises(ValidationError):
        TypeAdapter(ComputationSpec).validate_python(spec)


def test_drafts_do_not_publish_or_change_the_existing_integral(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Review preparation and public GET must not run a computation")
    monkeypatch.setattr("app.core.isolation.ComputationExecutor.run", forbidden)
    templates = load_templates()
    assert len(templates) == 15
    assert sum(template.review.status == "reviewed" for template in templates.values()) == 14
    original = json.loads((DEFAULT_DIRECTORY / "integral-endpoint.json").read_text(encoding="utf-8"))
    assert DRAFTS[11]["existing_template_snapshot"] == original
    assert templates["integral-endpoint"].review.status == "draft"
    assert all(DRAFTS[number]["id"] not in templates for number in range(12, 16))
    with TestClient(create_app()) as client:
        assert {item["id"] for item in client.get("/api/templates").json()} == set(templates)
        for number in range(12, 16):
            assert client.get("/api/templates/"+DRAFTS[number]["id"]).status_code == 404
