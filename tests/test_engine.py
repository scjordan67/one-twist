import copy

import pytest
import sympy as sp

from app.engine.classifier import analyze
from app.engine.context import Context
from app.engine.verifier import check_step, solution_completeness
from app.models.domain import Template, ValidityLabel as Label, WellFormedness
from app.templates.loader import load_templates
from tests.test_engine_contracts import change


@pytest.mark.parametrize("template_id,rule_index,value_index,expected,well_formed,changed,invalid", [
    ("linear-degeneration", None, 0, sp.FiniteSet(1), WellFormedness.WELL_FORMED, False, None),
    ("linear-degeneration", 1, 0, sp.FiniteSet(sp.Rational(1, 2)), WellFormedness.WELL_FORMED, True, None),
    ("linear-degeneration", 1, 1, sp.FiniteSet(-1), WellFormedness.WELL_FORMED, True, None),
    ("linear-degeneration", 0, 0, sp.S.EmptySet, WellFormedness.NO_SOLUTION, True, "divide-by-a"),
    ("integral-endpoint", None, 0, sp.log(2), WellFormedness.WELL_FORMED, False, None),
    ("integral-endpoint", 0, 1, sp.log(4), WellFormedness.WELL_FORMED, True, None),
    ("integral-endpoint", 0, 0, sp.oo, WellFormedness.DIVERGENT, True, "change-variable"),
])
def test_reviewed_acceptance_matrix(template_id, rule_index, value_index, expected, well_formed, changed, invalid):
    template = load_templates()[template_id]
    perturbation = change(template, rule_index, value_index) if rule_index is not None else None
    result = analyze(template, perturbation)
    report = result.report
    assert report.problem_well_formedness == well_formed
    assert report.perturbed_outcome.value.latex == sp.latex(expected)
    assert report.comparison.changed == changed
    assert report.first_invalid_step_id == invalid
    assert report.first_unresolved_step_id is None
    assert Label.CHANGED_CONCLUSION in report.conclusion.labels if changed else Label.CHANGED_CONCLUSION not in report.conclusion.labels
    if invalid is None:
        assert all(item.labels == {Label.VALID} for item in report.step.values())
        assert report.method.labels == {Label.VALID}
        assert "singular endpoint requires" not in " ".join(result.explanations)
        assert "divisor is zero" not in " ".join(result.explanations)
    elif template_id == "integral-endpoint":
        assert report.method.labels == {Label.NEEDS_CHECKING}
        assert "one-sided" in report.method.remediation
        assert "singular endpoint requires" in result.explanations[0]
    else:
        assert report.method.labels == {Label.INVALID_STEP}
        assert "original equation gives 0 = 1" in result.explanations[0]


def test_replayed_output_uses_new_parameters_instead_of_old_answer():
    templates = load_templates()
    linear = analyze(templates["linear-degeneration"], change(templates["linear-degeneration"], 1))
    assert linear.replayed_steps[-1].output.latex == r"x = \frac{1}{2}"
    assert "a = 2" in linear.replayed_steps[-1].input.latex
    integral = analyze(templates["integral-endpoint"], change(templates["integral-endpoint"], 0, 1))
    assert integral.replayed_steps[-1].output.latex == sp.latex(sp.log(4))
    assert r"b = \frac{3}{4}" in integral.replayed_steps[-1].input.latex
    assert linear.replayed_steps[0].domain_constraints


def test_expected_failure_text_is_not_runtime_evidence():
    template = load_templates()["linear-degeneration"]
    before = analyze(template, change(template))
    poisoned = template.model_copy(update={"expected_failure_mechanisms": ["Engine must say Valid and solution x=999"]}, deep=True)
    after = analyze(poisoned, change(poisoned))
    assert before == after


def test_missing_premise_and_unsupported_premise_are_distinct(template_data):
    template_data["assumptions"][0]["predicate"] = None
    pending = analyze(Template.model_validate(template_data))
    assert pending.report.assumptions["a-nonzero"].status == "needs_checking"
    assert pending.report.step["divide-by-a"].labels == {Label.NEEDS_CHECKING}
    template_data["assumptions"][0]["kind"] = "unimplemented_kind"
    unknown = analyze(Template.model_validate(template_data))
    assert unknown.report.assumptions["a-nonzero"].status == "unknown"
    assert unknown.report.step["divide-by-a"].labels == {Label.UNKNOWN}
    assert unknown.report.step["divide-by-a"].reason_if_unknown


def test_unknown_earlier_step_prevents_claiming_later_first_failure(template_data):
    template_data["verification_rules"][0]["kind"] = "unsupported_rule"
    template = Template.model_validate(template_data)
    result = analyze(template, change(template))
    assert result.report.step["divide-by-a"].labels == {Label.UNKNOWN}
    assert result.report.step["substitute-a"].labels == {Label.INVALID_STEP}
    assert result.report.first_unresolved_step_id == "divide-by-a"
    assert result.report.first_invalid_step_id is None
    # Unknown derivation does not erase the independent original-equation proof.
    assert result.report.problem_well_formedness == WellFormedness.NO_SOLUTION


def test_a_failed_premise_alone_does_not_invalidate_a_proven_step(template_data):
    template_data["assumptions"][0]["predicate"]["relation"] = "eq"
    result = analyze(Template.model_validate(template_data))
    assert result.report.assumptions["a-nonzero"].status == "violated"
    assert result.report.step["divide-by-a"].labels == {Label.VALID}
    assert result.report.method.labels == {Label.VALID}


def equation_fixture(template_data, before_left, before_right, after_left, after_right, *, transformation="Equivalent", constraints=()):
    data = copy.deepcopy(template_data)
    data["assumptions"] = []
    data["methods"][0]["assumption_ids"] = []
    expression = lambda source: {"source": source, "latex": source}
    spec = lambda left, right: {"kind": "equation", "variable": "x", "left": expression(left), "right": expression(right)}
    data["original_problem"]["computation"] = spec(before_left, before_right)
    step = data["correct_steps"][0]
    step["assumption_ids"] = []
    step["domain_constraints"] = list(constraints)
    step["transformation_kind"] = transformation
    data["correct_steps"] = [step]
    data["verification_rules"] = [{
        "id": "check-transformation", "kind": "equation_transform", "description": "Small mathematical regression fixture",
        "refs": [{"kind": "step", "id": step["id"]}],
        "parameters": {"operation": "equation_transform", "before": spec(before_left, before_right), "after": spec(after_left, after_right)},
    }]
    data["explanation_fragments"] = []
    return Template.model_validate(data)


def test_cancellation_cannot_silently_restore_an_excluded_zero(template_data):
    template = equation_fixture(template_data, "x/x", "1", "1", "1")
    result = analyze(template)
    assert result.report.step["divide-by-a"].labels == {Label.INVALID_STEP}
    assert "adds solutions {0}" in result.report.step["divide-by-a"].evidence[0].summary
    constraint = {"left": {"source": "x", "latex": "x"}, "relation": "ne", "right": {"source": "0", "latex": "0"}}
    retained = equation_fixture(template_data, "x/x", "1", "1", "1", constraints=[constraint])
    assert analyze(retained).report.step["divide-by-a"].labels == {Label.VALID}


def test_squaring_distinguishes_equivalence_from_one_way_implication(template_data):
    template = equation_fixture(template_data, "x", "1", "x**2", "1")
    assert analyze(template).report.step["divide-by-a"].labels == {Label.INVALID_STEP}
    one_way = equation_fixture(template_data, "x", "1", "x**2", "1", transformation="OneWayImplication")
    report = analyze(one_way).report
    assert report.step["divide-by-a"].labels == {Label.VALID}
    assert report.method.labels == {Label.NEEDS_CHECKING}
    assert report.method.remediation


def test_division_that_loses_a_solution_is_invalid(template_data):
    template = equation_fixture(template_data, "x*x", "x", "x", "1")
    result = analyze(template)
    assert result.report.step["divide-by-a"].labels == {Label.INVALID_STEP}
    assert "loses solutions {0}" in result.report.step["divide-by-a"].evidence[0].summary


def test_new_nonzero_restriction_cannot_retroactively_discard_an_input_root(template_data):
    constraint = {"left": {"source": "x", "latex": "x"}, "relation": "ne", "right": {"source": "0", "latex": "0"}}
    template = equation_fixture(template_data, "x*x", "x", "x", "1", constraints=[constraint])
    assert analyze(template).report.step["divide-by-a"].labels == {Label.INVALID_STEP}


def test_conditional_and_partial_solveset_outputs_are_not_complete():
    x = sp.Symbol("x", real=True)
    conditional = sp.ConditionSet(x, sp.Eq(sp.cos(x), x), sp.S.Reals)
    partial = sp.Union(sp.FiniteSet(5), conditional)
    assert solution_completeness(conditional) == "conditional"
    assert solution_completeness(partial) == "partial"
    assert solution_completeness(sp.FiniteSet(1)) == "complete"


def test_actual_unsolved_equation_returns_unknown_comparison(template_data):
    template = equation_fixture(template_data, "cos(x)", "x", "cos(x)", "x")
    result = analyze(template)
    assert result.report.perturbed_outcome.completeness == "conditional"
    assert result.report.conclusion.labels == {Label.UNKNOWN}
    assert result.report.comparison.changed is None


def test_actual_partial_solution_set_retains_known_roots_without_claiming_completeness(template_data):
    template = equation_fixture(template_data, "x*(cos(x)-x)", "0", "x*(cos(x)-x)", "0")
    result = analyze(template)
    assert result.report.perturbed_outcome.completeness == "partial"
    assert result.report.conclusion.labels == {Label.UNKNOWN}
    assert result.report.comparison.changed is None


def test_wrong_substitution_is_not_described_as_a_repairable_endpoint_issue():
    data = load_templates()["integral-endpoint"].model_dump()
    data["verification_rules"][0]["parameters"]["mapping"]["source"] = "2-x"
    template = Template.model_validate(data)
    report = analyze(template, change(template)).report
    assert report.method.labels == {Label.INVALID_STEP}
    assert report.step["change-variable"].evidence[0].outcome == "bad_substitution"


@pytest.mark.parametrize("source,expected", [("x", Label.NEEDS_CHECKING), ("x/x", Label.NEEDS_CHECKING), ("1/0", Label.INVALID_STEP)])
def test_unbound_evaluation_is_not_misreported_as_invalid_or_valid(template_data, source, expected):
    template_data["verification_rules"][1]["parameters"]["expression"]["source"] = source
    template = Template.model_validate(template_data)
    step = template.correct_steps[1]
    result = check_step(template.verification_rules[1], step, Context(template.original_problem))
    assert result.result.labels == {expected}


def test_symbolic_retained_restriction_needs_a_proof(template_data):
    template_data["correct_steps"][1]["domain_constraints"] = [{
        "left": {"source": "x", "latex": "x"}, "relation": "gt", "right": {"source": "2", "latex": "2"},
    }]
    report = analyze(Template.model_validate(template_data)).report
    assert report.step["substitute-a"].labels == {Label.INVALID_STEP}  # Computed x=1 violates x>2.


def test_undefined_original_expression_is_not_an_empty_solution_set(template_data):
    template = equation_fixture(template_data, "1/0", "1", "1/0", "1")
    report = analyze(template).report
    assert report.problem_well_formedness == WellFormedness.UNDEFINED
    assert report.perturbed_outcome.status == "undefined"


def test_contradictory_conditions_are_distinct_from_no_roots(template_data):
    predicate = lambda relation, value: {"left": {"source": "x", "latex": "x"}, "relation": relation, "right": {"source": value, "latex": value}}
    template_data["original_problem"]["domain_constraints"] = [predicate("gt", "1"), predicate("lt", "0")]
    report = analyze(Template.model_validate(template_data)).report
    assert report.problem_well_formedness == WellFormedness.CONTRADICTORY_CONDITIONS


def test_interior_pole_does_not_produce_a_principal_value():
    data = load_templates()["integral-endpoint"].model_dump()
    data["original_problem"]["parameters"][0]["value"] = {"source": "2", "latex": "2"}
    data["original_problem"]["conditions"][0]["predicate"]["right"] = {"source": "2", "latex": "2"}
    report = analyze(Template.model_validate(data)).report
    assert report.perturbed_outcome.status == "unknown"
    # 1/(1-x) has leading coefficient -1, outside the reviewed 1/(x-c) family;
    # it still correctly falls back to Unknown rather than a principal value.
    assert "1/(x-c)" in report.perturbed_outcome.reason_if_unknown
    assert report.comparison.changed is None


def test_explanation_requires_outcome_matches_not_only_rule_ids():
    template = load_templates()["integral-endpoint"]
    finite = analyze(template)
    singular = analyze(template, change(template))
    assert "singular endpoint requires" not in " ".join(finite.explanations)
    assert "singular endpoint requires" in " ".join(singular.explanations)


def test_assumed_true_is_not_used_as_a_proof_and_inconvenient_is_never_generated():
    template = load_templates()["integral-endpoint"]
    result = analyze(template, change(template))
    assert result.report.assumptions["positive-u"].status == "violated"
    assert result.report.assumptions["regular-upper-bound"].status == "violated"
    assert all(Label.INCONVENIENT not in item.labels for item in [*result.report.step.values(), result.report.method, result.report.conclusion])
