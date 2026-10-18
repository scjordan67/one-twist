"""Build the approved private packets into staging; no production publication."""
import json
from pathlib import Path

from app.models.domain import Template
from app.templates.loader import validate_expressions, validate_ivp_scopes

root = Path(__file__).resolve().parents[1]
staging = root / "docs/phase5/batch-03-runtime"
staging.mkdir(exist_ok=True)
for path in sorted((root / "docs/phase5/batch-03").glob("*.json")):
    draft = json.loads(path.read_text(encoding="utf-8"))
    number = draft["matrix_number"]
    if number == 11:
        content = draft["existing_template_snapshot"]
    else:
        problem = draft["original_problem"]
        problem["computation"] = draft["proposed_computation"]
        changes = [
            dict(id=item["id"], condition_id=item["condition_id"], type=item["type"],
                 description=item["description"], allowed_values=[item["new_value"]])
            for item in draft["allowed_changes"]
        ]
        rules = [
            dict(id="check-"+item["step_id"], kind=item["operation"],
                 refs=[dict(kind="step", id=item["step_id"])],
                 description="Recompute this finite claim from the actual problem.",
                 parameters={key: value for key, value in item.items() if key != "step_id"})
            for item in draft["planned_checks"]
        ]
        baseline = draft["scenarios"][0]["reference_outcome"]
        conclusion = baseline.get("value", baseline.get("formula"))
        content = dict(schema_version=1, id=draft["id"], title=draft["title"],
                       tags=[draft["topic"]], difficulty="advanced", original_problem=problem,
                       assumptions=draft["assumptions"], methods=draft["methods"],
                       correct_steps=draft["correct_steps"], conclusion=conclusion,
                       allowed_perturbations=changes, expected_failure_mechanisms=[
                           "Reviewed batch-03 finite mechanism; never runtime evidence."],
                       verification_rules=rules, explanation_fragments=[], review=draft["review"])
    template = Template.model_validate(content)
    validate_expressions(template, set(template.original_problem.variables) |
                         {item.name for item in template.original_problem.parameters})
    validate_ivp_scopes(template)
    (staging / (template.id+".json")).write_text(template.model_dump_json(indent=2)+"\n", encoding="utf-8")
    print(template.id)
