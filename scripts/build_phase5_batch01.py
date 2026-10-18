"""Convert the approved review packets to finite runtime templates.

Default: stage drafts outside the production loader. --publish is used only
after runtime/API acceptance and records the actual Claude Code approval.
No scenario expectation or reference answer becomes a runtime checker.
"""
import argparse
import copy
import json
from pathlib import Path

import sympy as sp

from app.core.parsing import parse_math
from app.models.domain import Template
from app.templates.loader import DEFAULT_DIRECTORY, load_templates

DRAFT_DIRECTORY = Path("docs/phase5/batch-01")
STAGING_DIRECTORY = Path("docs/phase5/batch-01-runtime")
REVIEW = {
    "status": "reviewed", "reviewer": "Claude Code",
    "basis": "Formal independent mathematical and typed-contract review approved by Claude Code on 2026-10-18. Runtime isolation/API acceptance completed before publication.",
}


def convert(draft):
    if draft["matrix_number"] == 1:
        return load_templates()["linear-degeneration"].model_dump(mode="json")
    baseline = next(item for item in draft["scenarios"] if item["id"] == "baseline")
    problem = copy.deepcopy(draft["original_problem"])
    problem["computation"] = draft["proposed_computation"]
    domain = draft["domain_condition"]
    if domain:
        selected = next(item for item in domain["choices"] if item["id"] == domain["baseline_choice_id"])
        assert problem["domain_constraints"] == selected["constraints"]
        problem["domain_constraints"] = []  # MOVE ownership; never leave a fixed copy.
        condition = next(item for item in problem["conditions"] if item["id"] == domain["condition_id"])
        condition["predicate"] = None
        condition["domain_binding"] = {
            "kind": "domain", "variable": domain["variable"],
            "current": {"number_system": selected["number_system"], "constraints": selected["constraints"]},
        }
    assumptions = copy.deepcopy(draft["assumptions"])
    for item in assumptions:
        if item["id"] in draft["planned_assumption_checks"]:
            item["check"] = draft["planned_assumption_checks"][item["id"]]
    perturbations = []
    for change in draft["allowed_changes"]:
        rule = {key: change[key] for key in ("id", "condition_id", "type", "description")}
        rule["allowed_values"] = [change["new_value"]] if change["new_value"] else []
        if change["type"] == "domain":
            choice = next(item for item in domain["choices"] if item["id"] == change["choice_id"])
            rule["domain_choices"] = [{
                "id": choice["id"], "label": change["description"],
                "domain": {"number_system": choice["number_system"], "constraints": choice["constraints"]},
            }]
        perturbations.append(rule)
    checks = []
    for check in draft["planned_checks"]:
        checks.append({
            "id": check["id"], "kind": check["parameters"]["operation"],
            "refs": [{"kind": "step", "id": check["step_id"]}],
            "description": f"Recompute {check['parameters']['operation']} for this step using the actual problem domain.",
            "parameters": check["parameters"],
        })
    reference = baseline["reference_outcome"]
    if reference["status"] == "solution_set":
        value = sp.FiniteSet(*(parse_math(item["source"]) for item in reference["values"]))
    else:
        value = parse_math(reference["value"]["source"])
    fragments = {
        2: ("check-cancellation", "solution_set_changed", "Cancelling a factor requires retaining its zero case whenever the problem domain admits it. The reduced linear calculation does not recover that lost root."),
        3: ("check-original-acceptance", "candidate_set_mismatch", "Squaring only creates candidates. Check them in the original equation or retain the required sign before using the reverse implication."),
        4: ("check-inverse-equivalence", "solution_set_changed", "The principal square-root branch cannot describe every preimage when the problem admits a negative branch. Restore the branch domain or include both signed roots."),
        5: ("check-real-log-identity", "undefined_identity_side", "The real logarithm product rule needs each factor positive. The original product may remain positive even when its split logarithms are undefined. For real nonzero t, 2*log(abs(t)) is a valid repair."),
    }
    rule_id, outcome, explanation = fragments[draft["matrix_number"]]
    return dict(
        schema_version=1, id=draft["id"], title=draft["title"], tags=[draft["topic"], draft["id"]],
        difficulty=draft["difficulty"], original_problem=problem, assumptions=assumptions,
        methods=draft["methods"], correct_steps=draft["correct_steps"],
        conclusion={"latex": sp.latex(value)}, allowed_perturbations=perturbations,
        expected_failure_mechanisms=[basis for case in draft["scenarios"] if case["expected_report"]["first_invalid_step_id"]
                                     for basis in case["mathematical_basis"]],
        verification_rules=checks,
        explanation_fragments=[{
            "id": "boundary-explanation", "evidence_keys": [rule_id],
            "when": [{"rule_id": rule_id, "outcome": outcome}], "text": explanation,
        }],
        review=draft["review"],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    directory = DEFAULT_DIRECTORY if args.publish else STAGING_DIRECTORY
    directory.mkdir(parents=True, exist_ok=True)
    for path in sorted(DRAFT_DIRECTORY.glob("*.json")):
        draft = json.loads(path.read_text(encoding="utf-8"))
        data = convert(draft)
        data["review"] = REVIEW if args.publish else dict(
            status="draft", reviewer=None, basis="Mathematics approved; staged runtime candidate pending isolation/API acceptance.",
        )
        template = Template.model_validate(data)
        (directory / f"{template.id}.json").write_text(template.model_dump_json(indent=2) + "\n", encoding="utf-8")
        if args.publish:
            draft["review"] = REVIEW
            path.write_text(json.dumps(draft, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{'Published' if args.publish else 'Staged'} five templates in {directory}")


if __name__ == "__main__":
    main()
