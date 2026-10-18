"""Independent mathematical checks of the five proposed, unreviewed derivations.

Display strings are pinned alongside the calculations: these tests do not parse
LaTeX, judge arbitrary samples, or replace independent content review.
"""
import pytest
import sympy as sp

from app.challenges.loader import load_challenges
from app.core.parsing import parse_math
from app.templates.loader import load_templates


@pytest.fixture(scope="module")
def samples():
    return load_challenges(load_templates()).samples


def residual(sample):
    symbols = {name: sp.Symbol(name, real=True) for name in sample.problem.variables}
    symbols.update({item.name: sp.Symbol(item.name, real=True) for item in sample.problem.parameters})
    values = {symbols[item.name]: parse_math(item.value.source) for item in sample.problem.parameters}
    spec = sample.problem.computation
    expression = parse_math(spec.left.source, symbols=symbols) - parse_math(spec.right.source, symbols=symbols)
    return symbols[spec.variable], expression.subs(values)


def keys(sample):
    return {(item.derivation.value, item.conclusion.value, item.step_id, item.assumption_id, item.reason_category.value)
            for item in sample.rubric.accepted_answers}


def test_sample_one_reversible_linear_solution(samples):
    sample = samples["sample-001"]
    assert [step.output.latex for step in sample.steps] == ["2x=1", r"x=\frac12", r"S=\left\{\frac12\right\}"]
    x, expression = residual(sample)
    assert sp.solveset(expression, x, domain=sp.S.Reals) == sp.FiniteSet(sp.Rational(1, 2))
    assert expression.subs(x, sp.Rational(1, 2)) == 0
    assert all(item.finding == "valid" for item in sample.annotations)
    assert keys(sample) == {("sound", "correct", None, None, "no_flaw")}


def test_sample_two_positive_endpoints_and_exact_integral(samples):
    sample = samples["sample-002"]
    assert [step.output.latex for step in sample.steps] == [
        r"\int_{1/4}^{1}\frac{1}{u}\,\mathrm{d}u", r"\log 1-\log\left(\frac14\right)", r"\log 4",
    ]
    spec = sample.problem.computation
    x, u, b = sp.symbols("x u b", real=True)
    integrand = parse_math(spec.integrand.source, symbols={"x": x, "u": u, "b": b})
    upper = sp.simplify(parse_math(sample.problem.parameters[0].value.source))
    assert upper == sp.Rational(3, 4)
    domain = sp.calculus.util.continuous_domain(integrand, x, sp.S.Reals)
    assert sp.Interval(0, upper).is_subset(domain)
    assert sp.integrate(integrand, (x, 0, upper)) == sp.log(4)
    assert sp.integrate(1/u, (u, sp.Rational(1, 4), 1)) == sp.log(4)
    assert parse_math(sample.rubric.actual_conclusion.source) == sp.log(4)
    assert keys(sample) == {("sound", "correct", None, None, "no_flaw")}


def test_sample_three_missing_sign_is_a_false_universal_conclusion_not_tool_unknown(samples):
    sample = samples["sample-003"]
    assert [step.output.latex for step in sample.steps] == [r"f(x)=\sqrt{x\cdot x}", "f(x)=x", r"\forall x\in\mathbb{R},\quad \sqrt{x^2}=x"]
    x = sp.Symbol("x", real=True)
    actual = parse_math(sample.rubric.actual_conclusion.source, symbols={"x": x})
    assert sp.sqrt(x*x) == actual == sp.Abs(x)
    assert sp.solveset(actual - x, x, domain=sp.S.Reals) == sp.Interval(0, sp.oo)
    assert actual.subs(x, -1) == 1 != -1
    assert actual.subs(x, 0) == 0  # nonzero is not the missing restriction
    assert sample.assumptions[0].predicate.relation == "ge"
    assert keys(sample) == {("not_sound", "incorrect", "step-002", "premise-001", "missing_sign_condition")}


def test_sample_four_wrong_equivalences_cancel_but_do_not_make_a_sound_proof(samples):
    sample = samples["sample-004"]
    assert [(step.input.latex, step.output.latex) for step in sample.steps] == [("2x=2", "x=1"), ("x=1", "x^2=1"), ("x^2=1", "x=1")]
    assert all(step.transformation_kind.value == "Equivalent" and not step.domain_constraints for step in sample.steps)
    x, expression = residual(sample)
    sets = [sp.solveset(item, x, domain=sp.S.Reals) for item in [expression, x-1, x*x-1, x-1]]
    assert sets == [sp.FiniteSet(1), sp.FiniteSet(1), sp.FiniteSet(-1, 1), sp.FiniteSet(1)]
    assert sets[0] == sets[-1] and sets[1] != sets[2] and sets[2] != sets[3]
    assert sample.rubric.actual_conclusion.latex == r"\{1\}"
    assert {item[:3] for item in keys(sample)} == {("not_sound", "correct", "step-002")}


def test_sample_five_squaring_is_valid_forward_but_accepting_the_extra_root_is_not(samples):
    sample = samples["sample-005"]
    assert [step.output.latex for step in sample.steps] == ["x=(x-2)^2", r"(x-1)(x-4)=0\ \Longleftrightarrow\ x\in\{1,4\}", r"S_{\mathrm{original}}=\{1,4\}"]
    assert sample.steps[0].transformation_kind.value == "OneWayImplication"
    assert [item.finding for item in sample.annotations] == ["valid", "valid", "invalid"]
    x, expression = residual(sample)
    original = sp.solveset(expression, x, domain=sp.S.Reals)
    candidates = sp.solveset(x-(x-2)**2, x, domain=sp.S.Reals)
    assert original == sp.FiniteSet(4)
    assert candidates == sp.FiniteSet(1, 4)
    assert original.is_subset(candidates)
    assert expression.subs(x, 1) == 2 and expression.subs(x, 4) == 0
    assert candidates & sp.Interval(2, sp.oo) == original
    assert sample.rubric.actual_conclusion.latex == r"\{4\}"
    assert {item[:3] for item in keys(sample)} == {("not_sound", "incorrect", "step-003")}
