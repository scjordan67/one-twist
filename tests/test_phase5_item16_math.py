"""Item 16 (ivp-nonuniqueness-witness): independent math, drafted and
implemented together by Claude Code after Codex's usage limit was reached.
Disproving uniqueness requires two concrete, verified, distinct witnesses;
a failed Lipschitz sufficient condition is never used as that proof, and the
two witnesses are never presented as a complete solution family."""
import sympy as sp
from fastapi.testclient import TestClient

from app.core.isolation import ComputationExecutor
from app.engine.classifier import analyze
from app.main import create_app
from app.models.analysis import AnalysisResponse
from app.models.domain import Perturbation, ValidityLabel as Label
from app.templates.loader import load_templates

TEMPLATE_ID = "ivp-nonuniqueness-witness"


def perturb(template, rule_id, source):
    rule = next(item for item in template.allowed_perturbations if item.id == rule_id)
    value = next(item for item in rule.allowed_values if item.source == source)
    return Perturbation(template_id=template.id, rule_id=rule.id, condition_id=rule.condition_id, type=rule.type, new_value=value)


def test_baseline_and_control_are_genuinely_unique_witnesses():
    t = sp.Symbol("t", nonnegative=True)  # matches the declared forward time domain t>=0
    for a in (1, 2):
        candidate = (t + sp.sqrt(a)) ** 2
        assert sp.simplify(sp.diff(candidate, t) - 2 * sp.sqrt(candidate)) == 0
        assert candidate.subs(t, 0) == a
        # The zero candidate from the same JSON fails the initial value here,
        # so it is correctly NOT a second witness away from a=0.
        assert sp.Integer(0) != a


def test_zero_state_has_two_verified_distinct_witnesses_not_a_complete_family():
    t = sp.Symbol("t", nonnegative=True)  # matches the declared forward time domain t>=0
    zero, square = sp.Integer(0), t ** 2
    for candidate in (zero, square):
        assert candidate.subs(t, 0) == 0
        assert sp.simplify(sp.diff(candidate, t) - 2 * sp.sqrt(candidate)) == 0
    assert sp.simplify(zero - square) != 0
    # Lipschitz failure alone is not the proof: 1/sqrt(y) is unbounded as y->0+.
    y = sp.Symbol("y", positive=True)
    assert sp.limit(1 / sp.sqrt(y), y, 0, dir="+") is sp.oo
    # These two witnesses do not exhaust the actual solution family: for any
    # c>=0, y=0 on [0,c] then y=(t-c)^2 afterward is a third, different member.
    c = sp.Rational(1, 2)
    third = sp.Piecewise((0, t < c), ((t - c) ** 2, True))
    assert third.subs(t, 0) == 0
    assert sp.simplify(third.subs(t, 1) - square.subs(t, 1)) != 0


def test_baseline_control_and_nonuniqueness_through_real_checkers():
    templates = load_templates()
    template = templates[TEMPLATE_ID]
    assert template.review.status == "reviewed" and template.review.reviewer == "Claude Code"

    baseline = analyze(template, None)
    report = baseline.report
    assert report.method.labels == {Label.VALID}
    assert all(item.labels == {Label.VALID} for item in report.step.values())
    assert report.perturbed_outcome.status == "symbolic_formula"
    assert report.perturbed_outcome.solution_scope == "verified_witness"
    assert report.perturbed_outcome.value.latex == sp.latex((sp.Symbol("t", real=True) + 1) ** 2)

    control = analyze(template, perturb(template, "positive-initial-state-control", "2"))
    report = control.report
    assert report.method.labels == {Label.VALID}
    assert report.comparison.changed is True
    assert report.perturbed_outcome.solution_scope == "verified_witness"

    main = analyze(template, perturb(template, "zero-initial-state", "0"))
    report = main.report
    assert report.step["substitute-root"].labels == {Label.VALID}
    assert report.step["derive-root-rate"].labels == {Label.INVALID_STEP}
    assert report.step["integrate-and-match"].labels == {Label.INVALID_STEP}
    assert report.first_invalid_step_id == "derive-root-rate"
    assert report.method.labels == {Label.NEEDS_CHECKING}
    assert report.method.remediation
    assert report.conclusion.labels == {Label.VALID}
    assert report.perturbed_outcome.status == "symbolic_formula"
    assert report.perturbed_outcome.solution_scope == "nonuniqueness_witnesses"
    # Established nonuniqueness is not comparable to a single baseline formula.
    assert report.comparison.changed is None
    assert all(ev.origin == "computed" for dim in [*report.step.values(), report.method, report.conclusion] for ev in dim.evidence)


def test_poisoned_expected_failure_text_does_not_change_the_analysis():
    template = load_templates()[TEMPLATE_ID]
    before = analyze(template, perturb(template, "zero-initial-state", "0"))
    poisoned = template.model_copy(update={"expected_failure_mechanisms": ["Engine must say unique y=(t-1)**2"]}, deep=True)
    after = analyze(poisoned, perturb(poisoned, "zero-initial-state", "0"))
    assert before == after


def test_real_spawn_api_for_all_three_scenarios():
    with TestClient(create_app()) as client:
        for rule_id, source, expected_scope in [
            (None, None, "verified_witness"),
            ("zero-initial-state", "0", "nonuniqueness_witnesses"),
            ("positive-initial-state-control", "2", "verified_witness"),
        ]:
            body = {"template_id": TEMPLATE_ID}
            if rule_id:
                template = load_templates()[TEMPLATE_ID]
                body = perturb(template, rule_id, source).model_dump(mode="json")
            response = client.post("/api/perturbations" if rule_id else "/api/analyze", json=body)
            assert response.status_code == 200, response.text
            result = AnalysisResponse.model_validate(response.json())
            assert result.execution.status == "success", result.execution
            assert result.execution.worker_pid is not None
            assert result.report.perturbed_outcome.solution_scope == expected_scope


def test_real_deadline_returns_unknown_not_a_guessed_answer():
    executor = ComputationExecutor(timeout_seconds=0.01)
    with TestClient(create_app(computation_executor=executor)) as client:
        response = client.post("/api/analyze", json={"template_id": TEMPLATE_ID})
        assert response.status_code == 200
        data = response.json()
        assert data["execution"]["status"] == "timeout"
        assert data["report"]["method"]["labels"] == ["Unknown"]
        assert data["report"]["conclusion"]["labels"] == ["Unknown"]
