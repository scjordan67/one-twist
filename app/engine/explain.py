from app.models.domain import Evidence, Template


def explain(template: Template, evidence: list[Evidence]) -> list[str]:
    observed = {(item.rule_id, item.outcome) for item in evidence}
    fragments = [
        fragment.text for fragment in template.explanation_fragments
        if fragment.when and all((item.rule_id, item.outcome) in observed for item in fragment.when)
    ]
    if fragments:
        return fragments
    # Deterministic facts only. No outcome is inferred from perturbation names,
    # authored expected-failure text, or a computation's running time.
    return list(dict.fromkeys(item.summary for item in evidence)) or ["No mathematical evidence has been established."]
