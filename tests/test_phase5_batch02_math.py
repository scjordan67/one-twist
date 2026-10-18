"""Approved draft mathematics, computed independently of runtime checkers."""
import json
from pathlib import Path

import pytest
import sympy as sp

from app.core.parsing import parse_math
from app.models.domain import Assumption, Method, Problem, Review, Step
from app.templates.loader import load_templates
from scripts.build_phase5_batch02 import scoped_assumptions


DIRECTORY = Path(__file__).resolve().parents[1] / "docs" / "phase5" / "batch-02"
DRAFTS = {data["matrix_number"]: data for path in DIRECTORY.glob("*.json")
          if (data := json.loads(path.read_text(encoding="utf-8")))}
x = sp.Symbol("x", real=True)


def value(source):
    return sp.simplify(parse_math(source))


def assert_numeric(outcome, expected):
    assert outcome["status"] == "numeric_value"
    assert sp.simplify(value(outcome["value"]["source"]) - expected) == 0


@pytest.mark.parametrize("number", range(6, 11))
def test_draft_references_and_single_condition_changes(number):
    draft = DRAFTS[number]
    review = Review.model_validate(draft["review"])
    assert review.status == "reviewed" and review.reviewer == "Claude Code"
    assert load_templates()[draft["id"]].review.status == "reviewed"
    problem = Problem.model_validate(draft["original_problem"])
    assumptions = [Assumption.model_validate(item) for item in scoped_assumptions(draft)]
    steps = [Step.model_validate(item) for item in draft["correct_steps"]]
    methods = [Method.model_validate(item) for item in draft["methods"]]
    condition_ids = {item.id for item in problem.conditions}
    assumption_ids = {item.id for item in assumptions}
    method_ids = {item.id for item in methods}
    assert len({item.id for item in steps}) == len(steps)
    assert [item.number for item in steps] == list(range(1, len(steps) + 1))
    assert all(set(item.condition_ids) <= condition_ids for item in assumptions)
    assert all(set(item.assumption_ids) <= assumption_ids for item in methods)
    assert all(item.method_id in method_ids and set(item.assumption_ids) <= assumption_ids for item in steps)
    assert {item["step_id"] for item in draft["planned_checks"]} == {item.id for item in steps}
    assert all(item["condition_id"] in condition_ids for item in draft["allowed_changes"])
    baseline = draft["scenarios"][0]["parameter_values"]
    assert {item.name: item.value.source for item in problem.parameters} == baseline
    for case in draft["scenarios"][1:]:
        assert sum(case["parameter_values"][key] != baseline[key] for key in baseline) == 1
        assert case["change_id"] in {item["id"] for item in draft["allowed_changes"]}
    names = {name: sp.Symbol(name, real=True) for name in [*problem.variables, *baseline]}

    def sources(node):
        if isinstance(node, dict):
            if node.get("source") is not None:
                parse_math(node["source"], symbols=names)
            for item in node.values():
                sources(item)
        elif isinstance(node, list):
            for item in node:
                sources(item)
    sources(draft)


@pytest.mark.parametrize("case", DRAFTS[6]["scenarios"], ids=lambda item: item["id"])
def test_06_complete_sine_roots_and_principal_branch(case):
    c, upper = (value(case["parameter_values"][key]) for key in ("c", "b"))
    roots = sp.solveset(sp.sin(x) - c, x, domain=sp.Interval.Ropen(0, upper))
    assert isinstance(roots, sp.FiniteSet)
    assert roots == sp.FiniteSet(*(value(item["source"]) for item in case["reference_outcome"]["values"]))
    principal = sp.FiniteSet(sp.asin(c))
    claim = sp.FiniteSet(*(value(item["source"]) for item in case["derivation_claim"]["values"]))
    assert principal == claim
    assert all(sp.simplify(sp.sin(root) - c) == 0 for root in principal)
    missing = roots - principal
    assert bool(missing) == (case["expected_report"]["first_invalid_step_id"] == "principal-inverse")
    assert case["expected_report"]["comparison"]["changed"] == (roots != sp.FiniteSet(sp.pi / 2))
    if missing:
        assert missing == sp.FiniteSet(5 * sp.pi / 6)


@pytest.mark.parametrize("case", DRAFTS[7]["scenarios"], ids=lambda item: item["id"])
def test_07_quadrant_sign_and_independent_calculations(case):
    theta = value(case["parameter_values"]["theta"])
    cosine = sp.cos(theta)
    positive_root = sp.sqrt(1 - sp.sin(theta) ** 2)
    assert sp.simplify(cosine ** 2 - (1 - sp.sin(theta) ** 2)) == 0
    assert positive_root == sp.Abs(cosine)
    assert_numeric(case["reference_outcome"], cosine)
    assert_numeric(case["derivation_claim"], positive_root)
    assert (positive_root != cosine) == (case["expected_report"]["first_invalid_step_id"] == "choose-positive-root")
    assert case["expected_report"]["comparison"]["changed"] == (cosine != sp.Rational(1, 2))


@pytest.mark.parametrize("case", DRAFTS[8]["scenarios"], ids=lambda item: item["id"])
def test_08_original_difference_quotients_and_punctured_identity(case):
    t = value(case["parameter_values"]["t"])
    f = sp.sqrt(x ** 2 + t ** 2)
    quotient = (f - f.subs(x, 0)) / x
    limits = {"left": sp.limit(quotient, x, 0, dir="-"), "right": sp.limit(quotient, x, 0, dir="+")}
    assert limits == {key: value(source) for key, source in case["one_sided_difference_quotients"].items()}
    assert sp.calculus.util.continuous_domain(f, x, sp.S.Reals) == sp.S.Reals
    # Check each side of the retained x != 0 domain, without authorizing evaluation at zero.
    for sign in (-1, 1):
        positive = sp.Symbol("h", positive=True)
        side_f = sp.sqrt(positive ** 2 + t ** 2)
        derivative_at_side = sp.diff(side_f, positive) * sign
        formula_at_side = sign * positive / sp.sqrt(positive ** 2 + t ** 2)
        assert sp.simplify(derivative_at_side - formula_at_side) == 0
    if limits["left"] == limits["right"]:
        assert_numeric(case["reference_outcome"], limits["left"])
        assert sp.simplify((x / sp.sqrt(x*x + t*t)).subs(x, 0)) == limits["left"]
    else:
        assert case["reference_outcome"]["status"] == "undefined"
        assert limits == {"left": -1, "right": 1}
        assert t == 0
    assert case["expected_report"]["problem_well_formedness"] == "WellFormed"
    assert case["expected_report"]["comparison"]["changed"] == (t == 0)


@pytest.mark.parametrize("case", DRAFTS[9]["scenarios"], ids=lambda item: item["id"])
def test_09_classification_has_independent_neighborhood_proof(case):
    a = value(case["parameter_values"]["a"])
    f = x ** 3 + a * x ** 2
    assert sp.diff(f, x).subs(x, 0) == 0
    assert sp.diff(f, x, 2).subs(x, 0) == 2 * a
    h = sp.Symbol("h", positive=True)
    if a > 0:
        assert sp.factor(f) == x*x*(x+a)
        # Entire punctured neighborhood (-a/2,a/2): x+a > a/2 > 0.
        negative_sign_region = sp.solve_univariate_inequality(x+a <= 0, x, relational=False)
        assert sp.Intersection(negative_sign_region, sp.Interval.open(-a/2, a/2)) == sp.S.EmptySet
        expected = "local_minimum"
    else:
        assert a == 0
        assert f.subs(x, h).is_positive is True
        assert f.subs(x, -h).is_negative is True
        expected = "stationary_non_extremum"
    assert case["reference_outcome"] == {"status": "classification", "classification": expected}
    assert case["expected_report"]["comparison"] == {"basis": "classification", "changed": a == 0}


@pytest.mark.parametrize("case", DRAFTS[10]["scenarios"], ids=lambda item: item["id"])
def test_10_original_limit_is_independent_of_derivative_ratio(case):
    t, k = (value(case["parameter_values"][key]) for key in ("t", "k"))
    numerator, denominator = x, k*x+t
    original_limits = [sp.limit(numerator/denominator, x, 0, dir=side) for side in ("-", "+")]
    ratio = sp.diff(numerator, x) / sp.diff(denominator, x)
    assert sp.diff(denominator, x) == k and k != 0
    assert original_limits[0] == original_limits[1]
    assert_numeric(case["reference_outcome"], original_limits[0])
    assert_numeric(case["derivation_claim"], ratio)
    zero_over_zero = sp.limit(numerator, x, 0) == 0 and sp.limit(denominator, x, 0) == 0
    assert (not zero_over_zero) == (case["expected_report"]["first_invalid_step_id"] == "replace-quotient-limit")
    assert (original_limits[0] != ratio) == (not zero_over_zero)
    assert case["expected_report"]["comparison"]["changed"] == (original_limits[0] != 1)
