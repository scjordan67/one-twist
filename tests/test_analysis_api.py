import os
from concurrent.futures import ThreadPoolExecutor

import pytest
import sympy as sp
from fastapi.testclient import TestClient

from app.core.isolation import ComputationExecutor
from app.main import create_app
from app.models.analysis import AnalysisResponse
from app.templates.loader import load_templates
from tests.isolation_workers import fixture_worker
from tests.test_engine_contracts import change
from tests.test_isolation import assert_reaped, request, wait_ready


@pytest.fixture
def client():
    with TestClient(create_app()) as client:
        yield client


@pytest.mark.parametrize("template_id", ["linear-degeneration", "integral-endpoint"])
def test_analysis_and_perturbation_share_real_spawn_recomputation(client, template_id):
    template = load_templates()[template_id]
    perturbation = change(template)
    a = client.post("/api/analyze", json={"template_id": template.id, "perturbation": perturbation.model_dump(mode="json")})
    b = client.post("/api/perturbations", json=perturbation.model_dump(mode="json"))
    assert a.status_code == b.status_code == 200
    first = AnalysisResponse.model_validate(a.json())
    second = AnalysisResponse.model_validate(b.json())
    assert first.execution.status == second.execution.status == "success"
    assert first.execution.worker_pid != os.getpid()
    assert first.execution.worker_pid != second.execution.worker_pid
    assert first.model_dump(exclude={"execution"}) == second.model_dump(exclude={"execution"})
    assert first.report.first_invalid_step_id is not None
    assert first.methods == template.methods
    assert first.report.comparison.changed is True
    assert "expected_failure_mechanisms" not in a.text
    assert client.app.state.computations.active_count == 0


@pytest.mark.parametrize("template_id", ["linear-degeneration", "integral-endpoint"])
def test_original_analysis_computes_actual_baseline(client, template_id):
    response = client.post("/api/analyze", json={"template_id": template_id})
    assert response.status_code == 200
    result = response.json()
    assert result["execution"]["status"] == "success"
    assert result["report"]["comparison"]["changed"] is False
    assert result["report"]["method"]["labels"] == ["Valid"]


@pytest.mark.parametrize("template_id,rule_index,value_index,expected", [
    ("linear-degeneration", 1, 0, sp.FiniteSet(sp.Rational(1, 2))),
    ("linear-degeneration", 1, 1, sp.FiniteSet(-1)),
    ("integral-endpoint", 0, 1, sp.log(4)),
])
def test_finite_changed_conclusions_remain_valid_through_real_workers(client, template_id, rule_index, value_index, expected):
    template = load_templates()[template_id]
    response = client.post("/api/perturbations", json=change(template, rule_index, value_index).model_dump(mode="json"))
    assert response.status_code == 200
    report = response.json()["report"]
    assert report["method"]["labels"] == ["Valid"]
    assert set(report["conclusion"]["labels"]) == {"Valid", "Changed Conclusion"}
    assert report["perturbed_outcome"]["value"]["latex"] == sp.latex(expected)
    assert report["comparison"]["changed"] is True


def test_requests_cannot_supply_verdicts_problem_specs_or_unknown_values(client):
    for extra in [{"report": {}}, {"original_problem": {}}, {"labels": ["Valid"]}, {"timeout_seconds": 999}]:
        response = client.post("/api/analyze", json={"template_id": "linear-degeneration", **extra})
        assert response.status_code == 422
    template = load_templates()["linear-degeneration"]
    data = change(template).model_dump(mode="json")
    data["new_value"] = {"source": "__import__('os').system('bad')", "latex": "0"}
    assert client.post("/api/perturbations", json=data).status_code == 422
    data["new_value"]["source"] = "0"
    data["condition_id"] = "absent"
    assert client.post("/api/perturbations", json=data).status_code == 422
    assert client.app.state.computations.active_count == 0


def test_missing_or_mismatched_template_ids_are_rejected(client):
    assert client.post("/api/analyze", json={"template_id": "absent"}).status_code == 404
    template = load_templates()["linear-degeneration"]
    assert client.post("/api/analyze", json={"template_id": "integral-endpoint", "perturbation": change(template).model_dump(mode="json")}).status_code == 422


def test_deadline_maps_to_unknown_without_any_stale_validity_or_answer():
    executor = ComputationExecutor(timeout_seconds=0.01)
    with TestClient(create_app(computation_executor=executor)) as client:
        response = client.post("/api/analyze", json={"template_id": "linear-degeneration"})
        assert response.status_code == 200
        result = response.json()
        assert result["execution"]["status"] == "timeout"
        assert result["report"]["first_invalid_step_id"] is None
        assert result["report"]["comparison"] is None
        for dimension in [*result["report"]["step"].values(), result["report"]["method"], result["report"]["conclusion"]]:
            assert dimension["labels"] == ["Unknown"]
            assert "deadline_exceeded" in dimension["reason_if_unknown"]
        assert all(step["output"]["source"] is None for step in result["replayed_steps"])
        assert result["methods"][0]["name"] == "Algebraic rearrangement"
        assert_reaped(executor, result["execution"]["worker_pid"])


def test_startup_resource_failure_maps_to_unknown_and_can_recover(monkeypatch):
    executor = ComputationExecutor()
    with TestClient(create_app(computation_executor=executor)) as client:
        with monkeypatch.context() as patch:
            def broken_pipe(*args, **kwargs):
                raise OSError("simulated resource shortage")
            patch.setattr(executor._context, "Pipe", broken_pipe)
            response = client.post("/api/analyze", json={"template_id": "linear-degeneration"})
        result = response.json()
        assert response.status_code == 200
        assert result["execution"]["error"] == "worker_start_failed"
        assert result["report"]["method"]["labels"] == ["Unknown"]
        assert_reaped(executor)
        assert client.post("/api/analyze", json={"template_id": "linear-degeneration"}).json()["execution"]["status"] == "success"


def test_public_analysis_returns_503_at_capacity_while_get_stays_responsive(tmp_path):
    executor = ComputationExecutor(timeout_seconds=10, _worker_target=fixture_worker)
    with TestClient(create_app(computation_executor=executor)) as client, ThreadPoolExecutor(max_workers=2) as threads:
        markers = [tmp_path / f"math-ready-{i}" for i in range(2)]
        tasks = [threads.submit(executor.run, request("loop", ready_path=str(marker))) for marker in markers]
        try:
            pids = [wait_ready(marker) for marker in markers]
            assert client.post("/api/analyze", json={"template_id": "linear-degeneration"}).status_code == 503
            assert client.get("/api/templates").status_code == 200
        finally:
            executor.close()
        assert all(task.result(timeout=2).status == "cancelled" for task in tasks)
    assert_reaped(executor, *pids)
