"""Independent draft mathematics, not a new engine or a claim of review approval.

The proposed contracts are design-only. Core snapshots reuse existing models;
domain ownership/checker proposals stay in private review packets.
"""
import json
from pathlib import Path

import pytest
import sympy as sp
from fastapi.testclient import TestClient

from app.core.parsing import parse_math
from app.main import create_app
from app.models.domain import Assumption, DimensionResult, Method, Problem, Review, Step
from app.templates.loader import load_templates

DIRECTORY = Path(__file__).resolve().parents[1] / "docs" / "phase5" / "batch-01"
DRAFTS = {data["matrix_number"]: data for path in sorted(DIRECTORY.glob("*.json"))
          if (data := json.loads(path.read_text(encoding="utf-8")))}
CASES = [(number, case["id"]) for number, draft in DRAFTS.items() for case in draft["scenarios"]]


def symbols(draft):
    problem = draft["original_problem"]
    return {name: sp.Symbol(name, real=True)
            for name in [*problem["variables"], *(item["name"] for item in problem["parameters"])]}


def arithmetic(draft, source, case):
    names = symbols(draft)
    values = {names[key]: sp.simplify(parse_math(value)) for key, value in case["parameter_values"].items()}
    return sp.simplify(parse_math(source, symbols=names).subs(values))


def predicate_set(draft, predicate, case):
    left = arithmetic(draft, predicate["left"]["source"], case)
    right = arithmetic(draft, predicate["right"]["source"], case)
    relation = {"eq": sp.Eq, "ne": sp.Ne, "lt": sp.Lt, "le": sp.Le, "gt": sp.Gt, "ge": sp.Ge}[predicate["relation"]](left, right)
    if relation is sp.S.true:
        return sp.S.Reals
    if relation is sp.S.false:
        return sp.S.EmptySet
    return relation.as_set()


def real_domain(draft, case):
    domain = sp.S.Reals
    for predicate in case["effective_domain_constraints"]:
        domain &= predicate_set(draft, predicate, case)
    return domain


def solutions(draft, spec, case, extra_constraints=()):
    variable = symbols(draft)[spec["variable"]]
    left, right = (arithmetic(draft, spec[key]["source"], case) for key in ("left", "right"))
    domain = real_domain(draft, case)
    domain &= sp.calculus.util.continuous_domain(left, variable, sp.S.Reals)
    domain &= sp.calculus.util.continuous_domain(right, variable, sp.S.Reals)
    for constraint in extra_constraints:
        domain &= predicate_set(draft, constraint, case)
    result = sp.solveset(left - right, variable, domain=domain)
    assert not result.has(sp.ConditionSet)
    return result


def reference_set(draft, outcome, case):
    assert outcome["status"] == "solution_set" and outcome["completeness"] == "complete"
    return sp.FiniteSet(*(arithmetic(draft, item["source"], case) for item in outcome["values"]))


def scenario(draft, id):
    return next(case for case in draft["scenarios"] if case["id"] == id)


@pytest.mark.parametrize("number", range(1, 6))
def test_approved_review_packets_have_consistent_references_and_sources(number):
    draft = DRAFTS[number]
    assert draft["draft_version"] == 1
    review = Review.model_validate(draft["review"])
    assert review.status == "reviewed" and review.reviewer == "Claude Code"
    problem = Problem.model_validate(draft["original_problem"])
    assumptions = [Assumption.model_validate(item | (
        {"check": draft["planned_assumption_checks"][item["id"]]} if item["id"] in draft["planned_assumption_checks"] else {}
    )) for item in draft["assumptions"]]
    methods = [Method.model_validate(item) for item in draft["methods"]]
    steps = [Step.model_validate(item) for item in draft["correct_steps"]]
    condition_ids = {item.id for item in problem.conditions}
    assumption_ids = {item.id for item in assumptions}
    method_ids = {item.id for item in methods}
    step_ids = {item.id for item in steps}
    assert len(step_ids) == len(steps) and len(assumption_ids) == len(assumptions)
    assert [item.number for item in steps] == list(range(1, len(steps) + 1))
    assert all(set(item.condition_ids) <= condition_ids for item in assumptions)
    assert all(set(item.assumption_ids) <= assumption_ids for item in methods)
    assert all(item.method_id in method_ids and set(item.assumption_ids) <= assumption_ids for item in steps)
    assert all(item["condition_id"] in condition_ids for item in draft["allowed_changes"])
    if number != 1:
        assert all(item.get("step_id", "") in step_ids for item in draft["planned_checks"])
    assert set(draft["planned_assumption_checks"]) <= assumption_ids

    def sources(value):
        if isinstance(value, dict):
            if "source" in value and "latex" in value and value["source"] is not None:
                parse_math(value["source"], symbols=symbols(draft))
            for item in value.values():
                sources(item)
        elif isinstance(value, list):
            for item in value:
                sources(item)

    sources(draft)
    for case in draft["scenarios"]:
        expected = case["expected_report"]
        assert set(expected["step"]) == step_ids
        for dimension in [*expected["step"].values(), expected["method"], expected["conclusion"]]:
            DimensionResult.model_validate(dimension)
        assert case["mathematical_basis"]


def test_draft_01_preserves_existing_reviewed_phase_implementation_without_auto_approval():
    template = load_templates()["linear-degeneration"]
    draft = DRAFTS[1]
    assert draft["id"] == template.id
    assert Problem.model_validate(draft["original_problem"]).model_dump() == template.original_problem.model_dump() | {"well_formedness": None}
    assert [Step.model_validate(item).model_dump() for item in draft["correct_steps"]] == [step.model_dump() for step in template.correct_steps]
    assert draft["planned_checks"] == [rule.model_dump(mode="json") for rule in template.verification_rules]
    assert template.review.status == draft["review"]["status"] == "reviewed"
    for case in draft["scenarios"]:
        zero = arithmetic(draft, "a", case) == 0
        expected = case["expected_report"]
        assert expected["first_invalid_step_id"] == ("divide-by-a" if zero else None)
        assert expected["method"]["labels"] == (["Invalid Step"] if zero else ["Valid"])
        assert all(item["labels"] == (["Invalid Step"] if zero else ["Valid"]) for item in expected["step"].values())
        if zero:
            assert case["derivation_claim"]["status"] == "undefined"
            assert solutions(draft, draft["proposed_computation"], case) == sp.S.EmptySet


@pytest.mark.parametrize("number,case_id", CASES)
def test_all_declared_scenarios_have_independently_computed_original_answers_and_comparisons(number, case_id):
    draft = DRAFTS[number]
    case = scenario(draft, case_id)
    baseline = scenario(draft, "baseline")
    if number != 5:
        spec = draft["proposed_computation"]
        computed = solutions(draft, spec, case)
        original = solutions(draft, spec, baseline)
        assert computed == reference_set(draft, case["reference_outcome"], case)
        changed = computed != original
        assert case["expected_report"]["comparison"]["basis"] == "symbolic_formula"
        assert case["expected_report"]["problem_well_formedness"] == ("NoSolution" if computed == sp.S.EmptySet else "WellFormed")
    else:
        source = draft["proposed_computation"]["expression"]["source"]
        computed = arithmetic(draft, source, case)
        original = arithmetic(draft, source, baseline)
        assert computed.is_real and computed.is_finite
        assert sp.simplify(computed - arithmetic(draft, case["reference_outcome"]["value"]["source"], case)) == 0
        changed = sp.simplify(computed - original) != 0
        assert case["expected_report"]["comparison"]["basis"] == "numeric_value"
        assert case["expected_report"]["problem_well_formedness"] == "WellFormed"
    assert case["expected_report"]["comparison"]["changed"] == changed
    assert set(case["expected_report"]["conclusion"]["labels"]) == ({"Valid", "Changed Conclusion"} if changed else {"Valid"})


@pytest.mark.parametrize("number", range(1, 6))
def test_every_allowed_change_changes_exactly_one_declared_independent_condition(number):
    draft = DRAFTS[number]
    baseline = scenario(draft, "baseline")
    changes = {item["id"]: item for item in draft["allowed_changes"]}
    assert {case["change_id"] for case in draft["scenarios"] if case["change_id"]} == set(changes)
    for case in draft["scenarios"][1:]:
        change = changes[case["change_id"]]
        if change["type"] == "domain":
            assert case["parameter_values"] == baseline["parameter_values"]
            assert case["effective_domain_constraints"] != baseline["effective_domain_constraints"]
            binding = draft["domain_condition"]
            assert binding["condition_id"] == change["condition_id"]
            choice = next(item for item in binding["choices"] if item["id"] == change["choice_id"])
            assert case["domain_choice_id"] == choice["id"]
            assert case["effective_domain_constraints"] == choice["constraints"]
            assert change["new_value"] is None
        else:
            changed_parameters = [name for name, value in baseline["parameter_values"].items() if value != case["parameter_values"][name]]
            assert len(changed_parameters) == 1
            name = changed_parameters[0]
            condition = next(item for item in draft["original_problem"]["conditions"] if item["id"] == change["condition_id"])
            assert condition["parameter_name"] == name
            assert case["parameter_values"][name] == change["new_value"]["source"]
            assert case["effective_domain_constraints"] == baseline["effective_domain_constraints"]
            assert change["choice_id"] is None


def test_02_cancelled_factor_loses_two_only_when_the_domain_admits_it():
    draft = DRAFTS[2]
    params = next(item["parameters"] for item in draft["planned_checks"] if item["id"] == "check-cancellation")
    before, after = params["before"], params["after"]
    retained = draft["correct_steps"][0]["domain_constraints"]
    assert retained[0]["relation"] == "ne" and retained[0]["right"]["source"] == "2"
    for case in draft["scenarios"]:
        actual = solutions(draft, before, case)
        reduced = solutions(draft, after, case, retained)
        lost = actual - reduced
        assert lost == (sp.FiniteSet(2) if case["id"] == "expanded" else sp.S.EmptySet)
        assert reduced == sp.FiniteSet(-1)
        expected = case["expected_report"]
        assert expected["step"]["solve-linear-factor"]["labels"] == ["Valid"]
        assert expected["first_invalid_step_id"] == ("cancel-x-minus-two" if lost else None)
        assert expected["step"]["cancel-x-minus-two"]["labels"] == (["Invalid Step"] if lost else ["Valid"])
        assert expected["step"]["claim-complete-set"]["labels"] == (["Invalid Step"] if lost else ["Valid"])
        assert expected["method"]["labels"] == (["Invalid Step"] if lost else ["Valid"])
        required = draft["planned_assumption_checks"]["factor-nonzero"]["required"]
        assert (real_domain(draft, case) - predicate_set(draft, required, case)).is_empty == (not bool(lost))
    x = symbols(draft)["x"]
    assert ((x-2)*(x+1)).subs(x, 2) == 0 and (x+1).subs(x, 2) != 0


def test_03_squaring_is_forward_valid_and_the_first_flaw_is_candidate_acceptance():
    draft = DRAFTS[3]
    assert draft["correct_steps"][0]["transformation_kind"] == "OneWayImplication"
    candidate_spec = draft["planned_checks"][1]["parameters"]["equation"]
    original_spec = draft["proposed_computation"]
    for case in draft["scenarios"]:
        actual = solutions(draft, original_spec, case)
        candidates = solutions(draft, candidate_spec, case)
        assert actual.is_subset(candidates)
        assert candidates == reference_set(draft, case["derivation_claim"], case)
        required = draft["planned_assumption_checks"]["rhs-nonnegative"]["required"]
        assert candidates & predicate_set(draft, required, case) == actual
        bad = candidates != actual
        expected = case["expected_report"]
        assert expected["step"]["square-forward"]["labels"] == ["Valid"]
        assert expected["step"]["solve-squared-equation"]["labels"] == ["Valid"]
        assert expected["first_invalid_step_id"] == ("accept-all-candidates" if bad else None)
        assert expected["step"]["accept-all-candidates"]["labels"] == (["Invalid Step"] if bad else ["Valid"])
        assert expected["method"]["labels"] == (["Invalid Step"] if bad else ["Valid"])
    case = scenario(draft, "extraneous-root")
    x = symbols(draft)["x"]
    residual = arithmetic(draft, "sqrt(x)-(x-c)", case)
    assert residual.subs(x, 4) == 4 and residual.subs(x, 9) == 0
    assert case["parameter_values"] == {"c": "6"}
    assert draft["correct_steps"][1]["output"]["latex"] == r"C=\{x\ge0:x=(x-c)^2\}"


def test_04_widened_domain_has_two_preimages_but_the_principal_branch_calculation_is_locally_valid():
    draft = DRAFTS[4]
    params = next(item["parameters"] for item in draft["planned_checks"] if item["id"] == "check-inverse-equivalence")
    retained = draft["correct_steps"][0]["domain_constraints"]
    for case in draft["scenarios"]:
        actual = solutions(draft, params["before"], case)
        branch = solutions(draft, params["after"], case, retained)
        assert branch == sp.FiniteSet(1)
        assert branch == reference_set(draft, case["derivation_claim"], case)
        bad = branch != actual
        expected = case["expected_report"]
        assert expected["step"]["evaluate-principal-root"]["labels"] == ["Valid"]
        assert expected["first_invalid_step_id"] == ("apply-principal-inverse" if bad else None)
        assert expected["step"]["apply-principal-inverse"]["labels"] == (["Invalid Step"] if bad else ["Valid"])
        assert expected["step"]["claim-all-preimages"]["labels"] == (["Invalid Step"] if bad else ["Valid"])
        assert expected["method"]["labels"] == (["Invalid Step"] if bad else ["Valid"])
    assert (-1)**2 == 1**2 and -1 != 1  # explicit injectivity counterexample
    u = sp.Symbol("u", nonnegative=True)
    h = sp.Symbol("h", positive=True)
    # If v=u+h, h>0, then v^2-u^2=h*(2u+h)>0 on the nonnegative branch.
    difference = sp.factor((u+h)**2-u**2)
    assert sp.simplify(difference - h*(2*u+h)) == 0
    assert difference.is_positive is True


def test_05_real_definedness_is_checked_before_rewriting_and_the_bad_derivation_preserves_the_original_value():
    draft = DRAFTS[5]
    t = symbols(draft)["t"]
    original_raw = parse_math("log(t*t)", symbols={"t": t})
    split_raw = parse_math("2*log(t)", symbols={"t": t})
    original_domain = sp.calculus.util.continuous_domain(original_raw, t, sp.S.Reals)
    split_domain = sp.calculus.util.continuous_domain(split_raw, t, sp.S.Reals)
    assert original_domain == sp.S.Reals - sp.FiniteSet(0)
    assert split_domain == sp.Interval.open(0, sp.oo)
    for case in draft["scenarios"]:
        value = arithmetic(draft, "t", case)
        assert original_domain.contains(value) is sp.S.true
        defined = split_domain.contains(value) is sp.S.true
        expected = case["expected_report"]
        assert expected["first_invalid_step_id"] == (None if defined else "split-real-log")
        assert all(item["labels"] == (["Valid"] if defined else ["Invalid Step"]) for item in expected["step"].values())
        assert expected["method"]["labels"] == (["Valid"] if defined else ["Invalid Step"])
        if defined:
            assert sp.simplify(arithmetic(draft, "log(t*t)", case) - arithmetic(draft, "2*log(t)", case)) == 0
        else:
            assert case["derivation_claim"]["status"] == "undefined"
            assert case["reference_outcome"] == scenario(draft, "baseline")["reference_outcome"]
    assert arithmetic(draft, "2*log(abs(t))", scenario(draft, "negative-factor")) == 0
    assert [step["output"]["latex"] for step in draft["correct_steps"]] == [r"2\log t", "0"]


def test_loading_public_content_publishes_only_accepted_batch_and_does_not_compute(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Loading review packets/public lists must not invoke mathematical workers")
    monkeypatch.setattr("app.core.isolation.ComputationExecutor.run", forbidden)
    assert len(DRAFTS) == 5 and set(DRAFTS) == set(range(1, 6))
    templates = load_templates()
    approved = {draft["id"] for draft in DRAFTS.values()}
    assert set(templates) == approved | {"integral-endpoint", "sine-principal-branch", "cosine-quadrant-sign",
                                        "derivative-cusp", "stationary-second-derivative", "lhopital-form",
                                        "integral-interior-pole", "integral-coalescing-poles",
                                        "ivp-zero-equilibrium", "ivp-principal-initial-root",
                                        "ivp-nonuniqueness-witness",
                                        "principal-argument-product", "real-square-to-complex-domain",
                                        "vector-angle-zero-norm", "line-intersection-all-coordinates"}
    assert all(templates[id].review.status == "reviewed" for id in approved)
    # integral-endpoint received its own formal re-review in batch 11-15.
    assert templates["integral-endpoint"].review.status == "reviewed"
    with TestClient(create_app()) as client:
        assert {item["id"] for item in client.get("/api/templates").json()} == set(templates)
        assert len(client.get("/api/challenges").json()) == 10
        for number in range(2, 6):
            assert client.get(f"/api/templates/{DRAFTS[number]['id']}").status_code == 200
