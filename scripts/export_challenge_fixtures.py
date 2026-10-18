"""Export test-only challenge fixtures through actual HTTP handlers and spawn workers.

Run: uv run --frozen python -m scripts.export_challenge_fixtures
Production frontend code never imports these fixtures.
"""
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from scripts.export_explorer_fixtures import normalize


def main():
    with TestClient(create_app()) as client:
        summaries = client.get("/api/challenges").json()
        details, feedbacks, answers = {}, {}, {}
        bank = client.app.state.challenges
        for item in summaries:
            id = item["id"]
            details[id] = client.get(f"/api/challenges/{id}").json()
            challenge = bank.challenges[id]
            if challenge.mode == "A":
                answer = challenge.accepted_answers[0].answer.model_dump(mode="json")
            elif challenge.mode == "B":
                template = bank.templates[challenge.template_id]
                rule = template.allowed_perturbations[0]
                answer = {"perturbation": {"template_id": template.id, "rule_id": rule.id, "condition_id": rule.condition_id,
                                           "type": rule.type, "new_value": rule.allowed_values[0].model_dump(mode="json")}}
            else:
                answer = bank.samples[challenge.sample_id].rubric.accepted_answers[0].model_dump(mode="json")
            answers[id] = dict(challenge_id=id, mode=challenge.mode, free_text=None, **answer)
            response = client.post("/api/challenges/check", json=answers[id])
            response.raise_for_status()
            feedback = response.json()
            assert feedback["grade"] == "Correct"
            if feedback["analysis"]:
                assert feedback["analysis"]["execution"]["status"] == "success"
                feedback["analysis"]["execution"] = None
            feedbacks[id] = feedback
    target = Path("frontend/src/test/challenge-fixtures.json")
    target.write_text(json.dumps(normalize(dict(summaries=summaries, details=details, feedbacks=feedbacks, answers=answers)), indent=2) + "\n", encoding="utf-8")
    print(f"Exported {len(details)} real API challenge fixtures to {target}")


if __name__ == "__main__":
    main()
