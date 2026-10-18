"""Small independent checks of the authored examples, not a runtime verifier."""

import sympy as sp

from app.core.parsing import parse_math
from app.templates.loader import load_templates


def test_linear_example_baseline_and_zero_branch():
    template = load_templates()["linear-degeneration"]
    x = sp.Symbol("x", real=True)
    original_a = parse_math(template.original_problem.parameters[0].value.source)
    assert sp.solveset(original_a * x - 1, x, domain=sp.S.Reals) == sp.FiniteSet(1)
    # Return to ax = 1, rather than trying to evaluate the invalid quotient 1/0.
    assert sp.solveset(0 * x - 1, x, domain=sp.S.Reals) == sp.S.EmptySet


def test_integral_example_original_value_and_singular_endpoint():
    template = load_templates()["integral-endpoint"]
    x = sp.Symbol("x", real=True)
    upper = parse_math(template.original_problem.parameters[0].value.source)
    expected = parse_math(template.conclusion.source)
    assert sp.simplify(sp.integrate(1 / (1 - x), (x, 0, upper)) - expected) == 0
    assert sp.limit(-sp.log(1 - x), x, 1, dir="-") == sp.oo


def test_changed_value_does_not_imply_method_failure():
    x = sp.Symbol("x", real=True)
    assert sp.solveset(2 * x - 1, x, domain=sp.S.Reals) == sp.FiniteSet(sp.Rational(1, 2))
    assert sp.simplify(sp.integrate(1 / (1 - x), (x, 0, sp.Rational(3, 4))) - sp.log(4)) == 0
