"""Stage approved 06-10 contracts; --publish follows real runtime acceptance."""
import argparse
import copy
import json
from pathlib import Path

import sympy as sp

from app.core.parsing import parse_math
from app.models.domain import Review, Template
from app.templates.loader import DEFAULT_DIRECTORY, load_templates

DIRECTORY = Path("docs/phase5/batch-02")
STAGING = Path("docs/phase5/batch-02-runtime")
REVIEW = dict(status="reviewed", reviewer="Claude Code",
              basis="Independent mathematical review of 06-10 approved by Claude Code on 2026-10-18. Runtime isolation/API acceptance completed before publication.")


def scoped_assumptions(draft):
    assumptions = copy.deepcopy(draft["assumptions"])
    checks = draft["planned_checks"]
    if draft["matrix_number"] == 6:
        assumptions[0]["check"] = dict(operation="principal_sine_coverage", equation=checks[0]["equation"])
    elif draft["matrix_number"] == 8:
        assumptions[0]["check"] = {key: value for key, value in checks[1].items() if key != "step_id"} | {"operation": "point_formula_defined"}
    elif draft["matrix_number"] == 10:
        assumptions[0]["check"] = {key: value for key, value in checks[1].items() if key != "step_id"} | {"operation": "lhopital_zero_over_zero"}
    return assumptions


def convert(draft):
    problem = copy.deepcopy(draft["original_problem"])
    problem["computation"] = draft["proposed_computation"]
    reference = draft["scenarios"][0]["reference_outcome"]
    if reference["status"] == "classification":
        conclusion = {"latex": r"\text{" + reference["classification"].replace("_", " ") + "}"}
    elif reference["status"] == "solution_set":
        conclusion = {"latex": sp.latex(sp.FiniteSet(*(parse_math(item["source"]) for item in reference["values"])))}
    else:
        conclusion = {"latex": sp.latex(parse_math(reference["value"]["source"]))}
    rules = [
        dict(id="check-"+item["step_id"], kind=item["operation"], refs=[dict(kind="step", id=item["step_id"])],
             description="Independently verify "+item["operation"]+" within its declared mathematical scope.",
             parameters={key: value for key, value in item.items() if key != "step_id"})
        for item in draft["planned_checks"]
    ]
    index, outcome, explanation = {
        6: (0, "missing_sine_branches", "A principal inverse supplies one branch. Retain both inverse-sine branches and all relevant periods before claiming completeness."),
        7: (1, "identity_false", "Taking a positive square root recovers the absolute value, not the sign of cosine. Use the actual quadrant."),
        8: (1, "invalid_point_substitution", "A punctured derivative identity does not authorize substitution at its excluded point. The original left and right difference quotients decide point differentiability."),
        9: (2, "classification_false", "A zero second derivative is inconclusive. Here opposite neighborhood increments independently disprove the original minimum claim."),
        10: (1, "limit_replacement_false", "Check the original limiting form before differentiating a quotient. A nonzero limiting denominator permits ordinary limit laws."),
    }[draft["matrix_number"]]
    data = dict(
        schema_version=1, id=draft["id"], title=draft["title"], tags=[draft["topic"], draft["id"]],
        difficulty="introductory", original_problem=problem, assumptions=scoped_assumptions(draft),
        methods=draft["methods"], correct_steps=draft["correct_steps"], conclusion=conclusion,
        allowed_perturbations=[{key: item[key] for key in ("id", "condition_id", "type", "description")} |
                               {"allowed_values": [item["new_value"]]} for item in draft["allowed_changes"]],
        verification_rules=rules,
        expected_failure_mechanisms=[basis for case in draft["scenarios"] if case["expected_report"]["first_invalid_step_id"]
                                     for basis in case["mathematical_basis"]],
        explanation_fragments=[dict(id="boundary-explanation", evidence_keys=[rules[index]["id"]],
                                    when=[dict(rule_id=rules[index]["id"], outcome=outcome)], text=explanation)],
        review=dict(status="draft", reviewer=None, basis="Mathematics approved; staged runtime candidate awaiting isolated API acceptance."),
    )
    names = [*problem["variables"], *(item["name"] for item in problem["parameters"])]
    def typeset(value):
        if isinstance(value, dict):
            if value.get("source") is not None and "latex" in value:
                value["latex"] = sp.latex(parse_math(value["source"], symbols=names).doit())
            for item in value.values():
                typeset(item)
        elif isinstance(value, list):
            for item in value:
                typeset(item)
    data = copy.deepcopy(data)
    typeset(data)
    return Template.model_validate(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    destination = DEFAULT_DIRECTORY if args.publish else STAGING
    destination.mkdir(parents=True, exist_ok=True)
    for path in sorted(DIRECTORY.glob("*.json")):
        draft = json.loads(path.read_text(encoding="utf-8"))
        template = convert(draft)
        if args.publish:
            template.review = Review.model_validate(REVIEW)
            draft["review"] = REVIEW
            path.write_text(json.dumps(draft, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        (destination / f"{template.id}.json").write_text(template.model_dump_json(indent=2)+"\n", encoding="utf-8")
    load_templates(destination)
    print("Published" if args.publish else "Staged", "five templates in", destination)


if __name__ == "__main__":
    main()
