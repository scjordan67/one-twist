"""Refresh frontend contract fixtures through real API/spawn computations.

Run from the repository root: uv run --frozen python -m scripts.export_explorer_fixtures
These files are test input only; the application always requests the backend.
"""
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def normalize(value):
    if isinstance(value, dict):
        return {key: sorted(item) if key == "labels" else normalize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize(item) for item in value]
    return value


def main():
    fixtures = {}
    with TestClient(create_app()) as client:
        summaries = client.get("/api/templates").json()
        for summary in summaries:
            template = client.get(f"/api/templates/{summary['id']}").json()
            baseline = client.post("/api/analyze", json={"template_id": summary["id"]})
            baseline.raise_for_status()
            baseline = baseline.json()
            assert baseline["execution"]["status"] == "success"
            baseline["execution"] = None
            changes = {}
            for rule in template["allowed_perturbations"]:
                selections = rule["domain_choices"] if rule["type"] == "domain" else rule["allowed_values"]
                for value in selections:
                    body = {
                        "template_id": summary["id"], "rule_id": rule["id"], "condition_id": rule["condition_id"],
                        "type": rule["type"], "new_value": None if rule["type"] == "domain" else value,
                    }
                    if rule["type"] == "domain":
                        body["choice_id"] = value["id"]
                    response = client.post("/api/perturbations", json=body)
                    response.raise_for_status()
                    data = response.json()
                    assert data["execution"]["status"] == "success"
                    data["execution"] = None
                    key = value["id"] if rule["type"] == "domain" else value["source"]
                    changes[f"{rule['id']}:{key}"] = data
            fixtures[summary["id"]] = {"template": template, "baseline": baseline, "changes": changes}
    target = Path("frontend/src/test/engine-fixtures.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(normalize({"summaries": summaries, "examples": fixtures}), indent=2) + "\n", encoding="utf-8")
    print(f"Exported {len(fixtures)} real API fixtures to {target}")


if __name__ == "__main__":
    main()
