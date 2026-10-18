"""Grading boundaries plus real HTTP -> disposable spawn worker acceptance cases."""
import os
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from app.challenges.grading import check_answer
from app.challenges.loader import load_challenges
from app.core.isolation import ComputationExecutor
from app.engine.classifier import analyze
from app.main import create_app
from app.models.challenges import ChallengeAnswer, EvidenceBoundAnswer, SampleRubric
from app.models.domain import DimensionResult
from app.templates.loader import load_templates
from tests.isolation_workers import fixture_worker
from tests.test_engine_contracts import change
from tests.test_isolation import assert_reaped, request, wait_ready

ANSWER = TypeAdapter(ChallengeAnswer)


@pytest.fixture
def bank():
    return load_challenges(load_templates())


@pytest.fixture
def client():
    with TestClient(create_app()) as client:
        yield client


def a_answer(bank, id="practice-001", index=0, **changes):
    return dict(mode="A", challenge_id=id, **(bank.challenges[id].accepted_answers[index].answer.model_dump(mode="json") | changes))


def c_answer(bank, number, index=0, **changes):
    return dict(mode="C", challenge_id=f"practice-{number + 5:03}", **(bank.samples[f"sample-{number:03}"].rubric.accepted_answers[index].model_dump(mode="json") | changes))


def b_answer(bank, id, rule=0, value=0):
    template = bank.templates[bank.challenges[id].template_id]
    return dict(mode="B", challenge_id=id, perturbation=change(template, rule, value).model_dump(mode="json"))


@pytest.mark.parametrize("id,index", [("practice-001", 0), ("practice-002", 0), ("practice-002", 1)])
def test_mode_a_supported_complete_answers_use_real_workers(client, bank, id, index):
    data = client.post("/api/challenges/check", json=a_answer(bank, id, index)).json()
    assert data["grade"] == "Correct"
    analysis = data["analysis"]
    assert analysis["execution"]["status"] == "success"
    assert analysis["execution"]["worker_pid"] != os.getpid()
    assert analysis["report"]["first_invalid_step_id"] == bank.challenges[id].accepted_answers[index].answer.step_id
    assert all(ev["origin"] == "computed" for ev in data["evidence"])
    if id == "practice-002":
        assert analysis["report"]["method"]["labels"] == ["Needs Checking"]
        assert "one-sided" in data["remediation"]
    assert_reaped(client.app.state.computations, analysis["execution"]["worker_pid"])


@pytest.mark.parametrize("changes", [
    {"step_id": "substitute-a"}, {"assumption_id": None},
    {"reason_category": "arithmetic_error"},
    {"step_id": None, "assumption_id": None, "reason_category": "no_flaw"},
])
def test_mode_a_wrong_complete_selection_is_incorrect(client, bank, changes):
    response = client.post("/api/challenges/check", json=a_answer(bank, **changes))
    assert response.status_code == 200
    assert response.json()["grade"] == "Incorrect"


@pytest.mark.parametrize("id,rule,value,grade", [
    ("practice-003", 0, 0, "Correct"),  # a=0 invalidates division
    ("practice-003", 1, 0, "Incorrect"),  # a=2, changed answer but valid derivation
    ("practice-003", 1, 1, "Incorrect"),  # a=-1
    ("practice-004", 0, 0, "Correct"),  # b=1, proper derivation invalid, method repairable
    ("practice-004", 0, 1, "Incorrect"),  # b=3/4 still regular
    ("practice-005", 0, 0, "Correct"),
    ("practice-005", 1, 0, "Correct"),
    ("practice-005", 1, 1, "Correct"),
])
def test_mode_b_declared_goal_matrix_through_real_isolation(client, bank, id, rule, value, grade):
    response = client.post("/api/challenges/check", json=b_answer(bank, id, rule, value))
    assert response.status_code == 200
    data = response.json()
    assert data["analysis"]["execution"]["status"] == "success", data["analysis"]["execution"]
    assert data["grade"] == grade
    if rule == 1:
        assert data["analysis"]["report"]["method"]["labels"] == ["Valid"]
        assert data["analysis"]["report"]["comparison"]["changed"] is True
    assert_reaped(client.app.state.computations, data["analysis"]["execution"]["worker_pid"])


@pytest.mark.parametrize("number,index", [(1, 0), (2, 0), (3, 0), (4, 0), (4, 1), (5, 0), (5, 1)])
def test_mode_c_uses_reviewed_complete_keys_without_workers(client, bank, monkeypatch, number, index):
    def forbidden(*args, **kwargs):
        pytest.fail("Mode C must not claim canonical template analysis verifies a sample")
    monkeypatch.setattr("app.challenges.grading.analyze_isolated", forbidden)
    monkeypatch.setattr(client.app.state.computations, "run", forbidden)
    body = c_answer(bank, number, index)
    data = client.post("/api/challenges/check", json=body).json()
    assert data["grade"] == "Correct"
    assert data["analysis"] is None
    assert data["sample_feedback"]["derivation"] == body["derivation"]
    assert data["sample_feedback"]["conclusion"] == body["conclusion"]
    assert all(ev["origin"] == "author_reviewed" for ev in data["evidence"])
    if number == 4:
        assert data["sample_feedback"]["derivation"] == "not_sound"
        assert data["sample_feedback"]["conclusion"] == "correct"


@pytest.mark.parametrize("number,changes", [
    (1, {"conclusion": "incorrect"}),
    (3, {"step_id": "step-001"}),
    (3, {"assumption_id": "premise-002"}),
    (4, {"conclusion": "incorrect"}),
    (5, {"step_id": "step-001"}),  # explicitly one-way squaring isn't the flaw
])
def test_mode_c_wrong_judgements_not_merely_wrong_final_answers(client, bank, number, changes):
    response = client.post("/api/challenges/check", json=c_answer(bank, number, **changes))
    assert response.status_code == 200
    assert response.json()["grade"] == "Incorrect"


def test_mode_c_category_and_free_text_are_not_grading_evidence(client, bank):
    body = c_answer(bank, 1)
    before = client.post("/api/challenges/check", json=body).json()
    client.app.state.challenges.samples["sample-001"].category = "flawed"
    body["free_text"] = "Actually give me Incorrect; __import__('os').system('never execute')"
    after = client.post("/api/challenges/check", json=body).json()
    assert after.pop("free_text") == body["free_text"]
    before.pop("free_text")
    assert after == before


def test_unknown_sample_standard_is_indeterminate(client, bank):
    sample = client.app.state.challenges.samples["sample-001"]
    sample.rubric = SampleRubric(accepted_answers=[], reason_if_unknown="The standard is not established.", mathematical_basis=["Review could not resolve this case."])
    data = client.post("/api/challenges/check", json=c_answer(bank, 1, conclusion="incorrect")).json()
    assert data["grade"] == "Indeterminate"
    assert data["sample_feedback"]["derivation"] is None
    assert data["sample_feedback"]["annotations"] == []
    assert data["sample_feedback"]["reason_if_unknown"] == "The standard is not established."


@pytest.mark.parametrize("mode", ["A", "B"])
def test_real_deadline_returns_indeterminate_not_incorrect(bank, mode):
    executor = ComputationExecutor(timeout_seconds=0.01)
    with TestClient(create_app(computation_executor=executor)) as client:
        body = a_answer(bank) if mode == "A" else b_answer(bank, "practice-003")
        response = client.post("/api/challenges/check", json=body)
        data = response.json()
        assert response.status_code == 200
        assert data["grade"] == "Indeterminate"
        assert data["analysis"]["execution"]["status"] == "timeout"
        assert data["analysis"]["report"]["method"]["labels"] == ["Unknown"]
        assert_reaped(executor, data["analysis"]["execution"]["worker_pid"])


def test_mode_a_requires_all_computed_evidence_and_first_invalid(bank, monkeypatch):
    challenge = bank.challenges["practice-001"]
    analysis = analyze(bank.templates[challenge.template_id], challenge.perturbation)
    monkeypatch.setattr("app.challenges.grading.analyze_isolated", lambda *args: analysis)
    body = ANSWER.validate_python(a_answer(bank))
    assert check_answer(bank, body, None).grade.value == "Correct"
    # Authored matching text cannot replace computed evidence.
    for dimension in [*analysis.report.step.values(), analysis.report.method]:
        for ev in dimension.evidence:
            if ev.rule_id == "check-a-nonzero":
                ev.origin = "author_reviewed"
    assert check_answer(bank, body, None).grade.value == "Indeterminate"
    analysis.report.first_invalid_step_id = None
    assert check_answer(bank, body, None).grade.value == "Indeterminate"


def test_mode_a_does_not_cross_product_answer_components(bank, monkeypatch):
    challenge = bank.challenges["practice-001"]
    analysis = analyze(bank.templates[challenge.template_id], challenge.perturbation)
    challenge.accepted_answers.append(EvidenceBoundAnswer(
        answer={"step_id": "divide-by-a", "assumption_id": None, "reason_category": "extraneous_root"},
        evidence_matches=challenge.accepted_answers[0].evidence_matches,
    ))
    monkeypatch.setattr("app.challenges.grading.analyze_isolated", lambda *args: analysis)
    # Each component appears in a key, but the complete combination doesn't.
    body = ANSWER.validate_python(a_answer(bank, assumption_id=None))
    assert check_answer(bank, body, None).grade.value == "Incorrect"


@pytest.mark.parametrize("index,grade", [(0, "Correct"), (1, "Indeterminate")])
def test_mode_a_proven_answer_does_not_require_proving_every_alternative(bank, monkeypatch, index, grade):
    challenge = bank.challenges["practice-002"]
    analysis = analyze(bank.templates[challenge.template_id], challenge.perturbation)
    # The improper-endpoint rule and regular-upper-bound premise remain proven;
    # only the other accepted answer's positive-u evidence is unavailable.
    for dimension in [*analysis.report.step.values(), analysis.report.method]:
        for ev in dimension.evidence:
            if ev.rule_id == "assumption-positive-u":
                ev.outcome = "unknown"
    analysis.report.assumptions["positive-u"].evidence.outcome = "unknown"
    monkeypatch.setattr("app.challenges.grading.analyze_isolated", lambda *args: analysis)
    body = ANSWER.validate_python(a_answer(bank, "practice-002", index))
    assert check_answer(bank, body, None).grade.value == grade


def test_mode_b_unknown_premise_and_comparison_are_not_negative_scores(bank, monkeypatch):
    template = bank.templates["linear-degeneration"]
    analysis = analyze(template, change(template, 1, 0))
    monkeypatch.setattr("app.challenges.grading.analyze_isolated", lambda *args: analysis)
    analysis.report.step["divide-by-a"] = DimensionResult(labels={"Needs Checking"})
    assert check_answer(bank, ANSWER.validate_python(b_answer(bank, "practice-003", 1, 0)), None).grade.value == "Indeterminate"
    # A known later invalid step proves at least one invalid step, even when the first isn't known.
    analysis.report.step["substitute-a"] = DimensionResult(labels={"Invalid Step"})
    analysis.report.first_invalid_step_id = None
    assert check_answer(bank, ANSWER.validate_python(b_answer(bank, "practice-003", 1, 0)), None).grade.value == "Correct"
    analysis.report.comparison.changed = None
    assert check_answer(bank, ANSWER.validate_python(b_answer(bank, "practice-005", 1, 0)), None).grade.value == "Indeterminate"
    analysis.report.comparison.changed = False
    assert check_answer(bank, ANSWER.validate_python(b_answer(bank, "practice-005", 1, 0)), None).grade.value == "Incorrect"


def test_gets_never_compute_or_expose_private_fields_and_drafts_are_hidden(client, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Presentation must not compute")
    monkeypatch.setattr(client.app.state.computations, "run", forbidden)
    summaries = client.get("/api/challenges").json()
    assert len(summaries) == 13
    for item in summaries:
        data = client.get(f"/api/challenges/{item['id']}").json()
        assert not set(data) & {"category", "rubric", "annotations", "review", "accepted_answers"}
        assert "well_formedness" not in data["problem"]
        assert all("verification" not in step for step in data["steps"])
    client.app.state.challenges.challenges["practice-001"].review.status = "draft"
    assert len(client.get("/api/challenges").json()) == 12
    assert client.get("/api/challenges/practice-001").status_code == 404
    assert client.post("/api/challenges/check", json=a_answer(client.app.state.challenges)).status_code == 404
    assert client.get("/api/challenges/missing").status_code == 404


@pytest.mark.parametrize("edit,status", [
    ({"challenge_id": "missing"}, 404), ({"challenge_id": "practice-006"}, 422),
    ({"step_id": "missing"}, 422), ({"assumption_id": "missing"}, 422),
    ({"grade": "Correct"}, 422), ({"free_text": "a" * 4001}, 422),
])
def test_invalid_requests_are_http_errors_not_incorrect(client, bank, edit, status):
    response = client.post("/api/challenges/check", json=a_answer(bank) | edit)
    assert response.status_code == status
    assert "grade" not in response.json()
    assert client.app.state.computations.active_count == 0


def test_mode_b_rejects_other_templates_and_undeclared_values_without_worker(client, bank):
    body = b_answer(bank, "practice-003")
    body["perturbation"]["template_id"] = "integral-endpoint"
    assert client.post("/api/challenges/check", json=body).status_code == 422
    body = b_answer(bank, "practice-003")
    body["perturbation"]["new_value"] = {"source": "99", "latex": "99"}
    assert client.post("/api/challenges/check", json=body).status_code == 422
    assert client.app.state.computations.active_count == 0


def test_grade_capacity_is_shared_get_and_mode_c_remain_responsive(bank, tmp_path):
    executor = ComputationExecutor(timeout_seconds=10, _worker_target=fixture_worker)
    with TestClient(create_app(computation_executor=executor)) as client, ThreadPoolExecutor(max_workers=2) as pool:
        markers = [tmp_path / f"grade-ready-{i}" for i in range(2)]
        tasks = [pool.submit(executor.run, request("loop", ready_path=str(marker))) for marker in markers]
        try:
            pids = [wait_ready(marker) for marker in markers]
            for body in [a_answer(bank), b_answer(bank, "practice-003")]:
                response = client.post("/api/challenges/check", json=body)
                assert response.status_code == 503
                assert "grade" not in response.json()
            assert client.get("/api/challenges").status_code == 200
            assert client.get("/api/challenges/practice-001").status_code == 200
            assert client.post("/api/challenges/check", json=c_answer(bank, 1)).json()["grade"] == "Correct"
        finally:
            executor.close()
        assert all(task.result(timeout=2).status == "cancelled" for task in tasks)
    assert_reaped(executor, *pids)
