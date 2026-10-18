"""Evidence-based orchestration of the finite checkers, independent dimensions."""

import sympy as sp

from app.engine.assumptions import check_assumption
from app.engine.context import Context, UnsupportedMath, equal_sets, truth
from app.engine.explain import explain
from app.engine.perturbation import construct_problem
from app.engine.verifier import ProblemEvaluation, StepCheck, check_step, evaluate_problem
from app.models.analysis import AnalysisResponse, PerturbedProblem
from app.models.domain import (
    AssumptionState, ConclusionComparison, ConclusionResult, DimensionResult, Evidence, EvidenceRef,
    MathExpression, Perturbation, Template, ValidityLabel as Label, ValidityReport,
)


def merge(results: list[DimensionResult]) -> DimensionResult:
    labels = set().union(*(item.labels for item in results))
    if Label.INVALID_STEP in labels:
        chosen = Label.INVALID_STEP
    elif Label.UNKNOWN in labels:
        chosen = Label.UNKNOWN
    elif Label.NEEDS_CHECKING in labels:
        chosen = Label.NEEDS_CHECKING
    else:
        chosen = Label.VALID
    return DimensionResult(
        labels={chosen}, evidence=[ev for item in results for ev in item.evidence],
        affected_refs=[ref for item in results for ref in item.affected_refs],
        reason_if_unknown=("; ".join(dict.fromkeys(item.reason_if_unknown for item in results if item.reason_if_unknown)) or None) if chosen == Label.UNKNOWN else None,
        remediation=" ".join(dict.fromkeys(item.remediation for item in results if item.remediation)) or None,
    )


def comparison(original: ProblemEvaluation, changed: ProblemEvaluation) -> ConclusionComparison:
    left, right = original.result, changed.result
    established = all(
        result.status != "unknown" and result.completeness not in {"partial", "conditional"}
        for result in (left, right)
    )
    different = None
    if established:
        if left.status != right.status:
            different = True
        elif left.status == "classification":
            different = left.classification != right.classification
        elif left.status == "symbolic_formula":
            if left.solution_scope == right.solution_scope and left.variable == right.variable and left.time_domain == right.time_domain:
                difference = sp.simplify((original.value-changed.value).doit())
                # Compare formulas as identities. A nonzero polynomial may
                # vanish at isolated times without being the zero function.
                equal = (sp.Poly(difference, *sorted(difference.free_symbols, key=sp.default_sort_key)).is_zero
                         if difference.free_symbols and difference.is_polynomial() else difference.is_zero)
                different = None if equal is None else not equal
        elif left.status == "line_relation":
            # Compare the typed relation/point, never t/s parameters or LaTeX:
            # a control may be a pure re-parametrization of the same line.
            different = left.line_relation != right.line_relation
        elif original.value is not None and changed.value is not None:
            equal = equal_sets(original.value, changed.value) if left.status == "solution_set" else truth(sp.Eq(original.value, changed.value))
            if equal is None and left.status == "numeric_value":
                equal = (sp.simplify(original.value - changed.value)).is_zero
            different = None if equal is None else not equal
    basis = (
        "line_relation" if "line_relation" in {left.status, right.status} else
        "classification" if "classification" in {left.status, right.status} else
        "symbolic_formula" if {"solution_set", "symbolic_formula"} & {left.status, right.status} else "numeric_value"
    )
    return ConclusionComparison(
        basis=basis, original=left.value or MathExpression(latex=r"\text{Unknown}"), perturbed=right.value,
        changed=different,
    )


def _conclusion(evaluation: ProblemEvaluation, compared: ConclusionComparison) -> DimensionResult:
    result = evaluation.result
    unresolved = result.status == "unknown" or result.completeness in {"partial", "conditional"}
    labels = {Label.UNKNOWN} if unresolved else {Label.VALID}
    if compared.changed is True:
        labels.add(Label.CHANGED_CONCLUSION)
    evidence = [*evaluation.evidence, Evidence(rule_id="problem-evaluation", outcome=result.status,
                         summary=f"The new problem independently yields {result.status}: {result.value.latex if result.value else result.reason_if_unknown}.")]
    if compared.changed is not None:
        evidence.append(Evidence(rule_id="conclusion-comparison", outcome="changed" if compared.changed else "unchanged",
                                 summary=f"Comparison basis: {compared.basis}; changed: {compared.changed}."))
    return DimensionResult(labels=labels, evidence=evidence,
                           reason_if_unknown=(result.reason_if_unknown or "Solution set is incomplete") if unresolved else None)


def unverified_response(template: Template, perturbed: PerturbedProblem, reason: str) -> AnalysisResponse:
    """Boundary fallback: a timed out/crashed worker contributes no verdicts."""
    def unknown(refs=()):
        return DimensionResult(labels={Label.UNKNOWN}, reason_if_unknown=reason,
                               affected_refs=list(refs), evidence=[Evidence(rule_id="execution", outcome="unknown", summary=reason)])
    steps = {}
    replayed = []
    for step in template.correct_steps:
        result = unknown([EvidenceRef(kind="step", id=step.id)])
        steps[step.id] = result
        replayed.append(step.model_copy(update={
            "verification": result, "output": MathExpression(latex=r"\text{Not verified}"), "explanation": reason,
        }, deep=True))
    outcome = ConclusionResult(status="unknown", reason_if_unknown=reason)
    report = ValidityReport(
        step=steps, method=unknown(), conclusion=unknown(), original_outcome=outcome,
        perturbed_outcome=outcome, first_unresolved_step_id=template.correct_steps[0].id,
    )
    return AnalysisResponse(template_id=template.id, original_problem=template.original_problem,
                            perturbed=perturbed, replayed_steps=replayed, methods=template.methods, report=report, explanations=[reason])


def analyze(template: Template, perturbation: Perturbation | None = None) -> AnalysisResponse:
    perturbed = construct_problem(template, perturbation)
    try:
        original_context, context = Context(template.original_problem), Context(perturbed.problem)
    except (UnsupportedMath, ValueError, TypeError, NotImplementedError) as exc:
        return unverified_response(template, perturbed, str(exc))
    original = evaluate_problem(original_context)
    changed = evaluate_problem(context)
    compared = comparison(original, changed)
    assumptions = {item.id: check_assumption(item, context) for item in perturbed.assumptions}
    for assumption in perturbed.assumptions:
        # Removal remains a distinct event even if another fact establishes or
        # refutes the predicate. Neither assumed_true nor unchecked is proof.
        if assumption.state != AssumptionState.PERTURBED_REMOVED:
            status = assumptions[assumption.id].status
            assumption.state = AssumptionState.ASSUMED_TRUE if status == "satisfied" else (
                AssumptionState.PERTURBED_FALSE if status == "violated" and perturbation is not None else AssumptionState.UNCHECKED
            )
    steps = {}
    replayed = []
    checks: list[StepCheck] = []
    for step in template.correct_steps:
        rules = [rule for rule in template.verification_rules if any(ref.kind == "step" and ref.id == step.id for ref in rule.refs)]
        current = [check_step(rule, step, context) for rule in rules]
        if not current:
            current = [StepCheck(DimensionResult(labels={Label.UNKNOWN}, reason_if_unknown="No verification rule for this step"))]
        checks.extend(current)
        parts = [item.result for item in current]
        for assumption_id in step.assumption_ids:
            premise = assumptions[assumption_id]
            if premise.status in {"needs_checking", "unknown"}:
                parts.append(DimensionResult(
                    labels={Label.UNKNOWN if premise.status == "unknown" else Label.NEEDS_CHECKING},
                    reason_if_unknown=premise.reason if premise.status == "unknown" else None,
                    evidence=[premise.evidence], affected_refs=[EvidenceRef(kind="assumption", id=assumption_id)],
                ))
            else:
                # A violated premise is evidence, not an automatic step or
                # method failure. The mathematical rule must establish failure.
                parts.append(DimensionResult(labels={Label.VALID}, evidence=[premise.evidence]))
        result = merge(parts)
        steps[step.id] = result
        successful = Label.VALID in result.labels
        output = next((item.output for item in reversed(current) if item.output is not None), None)
        input_expression = next((item.input for item in current if item.input is not None), step.input)
        replayed.append(step.model_copy(update={
            "input": input_expression,
            "output": output if successful and output is not None else MathExpression(latex=r"\text{Not replayed as a valid step}"),
            "verification": result,
            "explanation": " ".join(item.summary for item in result.evidence) or result.reason_if_unknown or "Further premises need checking.",
        }, deep=True))
    first_unresolved = next((step.id for step in template.correct_steps if steps[step.id].labels & {Label.UNKNOWN, Label.NEEDS_CHECKING}), None)
    first_invalid = None
    for step in template.correct_steps:
        if step.id == first_unresolved:
            break
        if Label.INVALID_STEP in steps[step.id].labels:
            first_invalid = step.id
            break
    method = merge(list(steps.values()))
    invalid_checks = [item for item in checks if Label.INVALID_STEP in item.result.labels]
    unresolved = any(result.labels & {Label.UNKNOWN, Label.NEEDS_CHECKING} for result in steps.values())
    supported_repair = changed.result.status in {"numeric_value", "divergent"} or (
        changed.result.status == "symbolic_formula" and all(item.repair_verified for item in invalid_checks))
    if invalid_checks and all(item.repairable for item in invalid_checks) and not unresolved and supported_repair:
        method.labels = {Label.NEEDS_CHECKING}
    elif Label.VALID in method.labels and any(item.result.remediation for item in checks):
        method.labels = {Label.NEEDS_CHECKING}
    for assumption_id in {identifier for method_spec in template.methods for identifier in method_spec.assumption_ids}:
        premise = assumptions[assumption_id]
        if premise.status in {"unknown", "needs_checking"}:
            method = merge([method, DimensionResult(
                labels={Label.UNKNOWN if premise.status == "unknown" else Label.NEEDS_CHECKING},
                evidence=[premise.evidence], reason_if_unknown=premise.reason if premise.status == "unknown" else None,
            )])
    evidence = [ev for result in steps.values() for ev in result.evidence]
    for rule in template.verification_rules:
        if any(ref.kind == "step" for ref in rule.refs):
            continue
        if rule.kind in {"solution_set", "one_sided_limit"}:
            outcome = "no_solution" if changed.well_formedness and changed.well_formedness.value == "NoSolution" else changed.result.status
            evidence.append(Evidence(rule_id=rule.id, outcome=outcome, summary=f"Independent problem check: {outcome}."))
        else:
            unknown = DimensionResult(labels={Label.UNKNOWN}, reason_if_unknown=f"Unsupported verification rule: {rule.kind}")
            method = merge([method, unknown])
    conclusion = _conclusion(changed, compared)
    evidence.extend(conclusion.evidence)
    perturbed.problem.well_formedness = changed.well_formedness
    report = ValidityReport(
        problem_well_formedness=changed.well_formedness, step=steps, method=method, conclusion=conclusion,
        comparison=compared, assumptions=assumptions, original_outcome=original.result, perturbed_outcome=changed.result,
        first_invalid_step_id=first_invalid, first_unresolved_step_id=first_unresolved,
    )
    return AnalysisResponse(template_id=template.id, original_problem=template.original_problem,
                            perturbed=perturbed, replayed_steps=replayed, methods=template.methods, report=report,
                            explanations=explain(template, evidence))
