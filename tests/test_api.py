import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.templates.loader import TemplateLoadError


@pytest.fixture
def client():
    with TestClient(create_app()) as client:
        yield client


def test_lists_real_templates(client):
    response = client.get("/api/templates")
    assert response.status_code == 200
    assert {item["id"] for item in response.json()} == {"linear-degeneration", "integral-endpoint", "cancelled-factor-domain",
                                                      "squared-candidates-sign", "inverse-square-domain", "real-log-product",
                                                      "sine-principal-branch", "cosine-quadrant-sign", "derivative-cusp",
                                                      "stationary-second-derivative", "lhopital-form",
                                                      "integral-interior-pole", "integral-coalescing-poles",
                                                      "ivp-zero-equilibrium", "ivp-principal-initial-root",
                                                      "ivp-nonuniqueness-witness",
                                                      "principal-argument-product", "real-square-to-complex-domain",
                                                      "vector-angle-zero-norm", "line-intersection-all-coordinates"}


@pytest.mark.parametrize("template_id", ["linear-degeneration", "integral-endpoint"])
def test_detail_exposes_only_public_content(client, template_id):
    response = client.get(f"/api/templates/{template_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["original_problem"]["expression"]["latex"]
    assert data["allowed_perturbations"]
    assert not set(data) & {
        "correct_steps", "conclusion", "expected_failure_mechanisms",
        "verification_rules", "explanation_fragments", "assumptions",
    }


def test_unknown_template_returns_404(client):
    assert client.get("/api/templates/absent").status_code == 404


def test_challenge_grading_rejects_forged_verdicts(client):
    response = client.post("/api/challenges/check", json={"labels": ["Valid"]})
    assert response.status_code == 422


def test_bad_repository_fails_at_startup(tmp_path):
    with pytest.raises(TemplateLoadError):
        with TestClient(create_app(tmp_path)):
            pass
