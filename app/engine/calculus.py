"""Finite real calculus facts; no authored outcomes or theorem names are proof."""
from dataclasses import dataclass

import sympy as sp

from app.engine.context import Context, UnsupportedMath, subset, truth
from app.models.domain import DerivativeAtPointSpec, LimitSpec, StationaryPointSpec


def real_point(context, variable, point):
    symbol = context.symbols[variable]
    value = context.expr(point)
    if context.problem.variables[variable] != "real" or value.free_symbols or value.is_real is not True or value.is_finite is not True:
        raise UnsupportedMath("Calculus requires a real variable and a closed finite real point")
    return symbol, value


def one_sided(expression, variable, point, side):
    result = sp.simplify(sp.limit(expression, variable, point, dir=side))
    if result.has(sp.Limit, sp.nan, sp.zoo) or result.free_symbols:
        raise UnsupportedMath("A one-sided limit remains unresolved")
    if result not in (sp.oo, -sp.oo) and (result.is_finite is not True or result.is_real is not True):
        raise UnsupportedMath("Limit is not established real or infinite")
    return result


def punctured_neighborhood(domain, point, direction="both"):
    boundary = domain.boundary
    if not isinstance(boundary, sp.FiniteSet) and boundary is not sp.S.EmptySet:
        raise UnsupportedMath("Only finite-boundary neighborhoods are supported")
    distances = [sp.Abs(item-point) for item in boundary if item.is_finite is True and item != point]
    if any(item.is_positive is not True for item in distances):
        raise UnsupportedMath("Neighborhood boundary ordering is unresolved")
    radius = sp.Min(sp.Integer(1), *distances) / 2
    required = []
    if direction in {"both", "left"}:
        required.append(sp.Interval.open(point-radius, point))
    if direction in {"both", "right"}:
        required.append(sp.Interval.open(point, point+radius))
    if any(subset(interval, domain) is not True for interval in required):
        raise UnsupportedMath("Required punctured neighborhood is not in the expression's actual domain")


@dataclass
class DerivativeFacts:
    function: sp.Expr
    variable: sp.Symbol
    point: sp.Expr
    left: sp.Expr
    right: sp.Expr
    value: sp.Expr | None


def point_derivative(context: Context, spec: DerivativeAtPointSpec):
    variable, point = real_point(context, spec.variable, spec.point)
    raw = context.raw(spec.expression)
    # Recognize the actual reviewed family, not an authored family label.
    if point != 0 or not raw.is_Pow or raw.exp != sp.Rational(1, 2):
        raise UnsupportedMath("Point-derivative verification currently supports sqrt(x*x+q) at zero only")
    q = sp.simplify(raw.base.doit() - variable**2)
    if q.free_symbols or q.is_finite is not True or q.is_nonnegative is not True:
        raise UnsupportedMath("The actual radicand is not x*x plus a known finite nonnegative constant")
    if context.admissible_domain(variable) != sp.S.Reals or context.domain(spec.expression, variable) != sp.S.Reals:
        raise UnsupportedMath("This point-derivative family currently requires the full real problem domain")
    function = context.expr(spec.expression)
    h = sp.Dummy("h", real=True)
    quotient = (function.subs(variable, point+h) - function.subs(variable, point)) / h
    left, right = (one_sided(quotient, h, 0, side) for side in ("-", "+"))
    equal = truth(sp.Eq(left, right))
    if equal is None:
        raise UnsupportedMath("Equality of difference-quotient limits is unresolved")
    value = left if equal and left.is_finite is True else None
    return DerivativeFacts(function, variable, point, left, right, value)


@dataclass
class StationaryFacts:
    first: sp.Expr
    second: sp.Expr
    classification: str
    proof: str


def stationary_facts(context: Context, spec: StationaryPointSpec):
    variable, point = real_point(context, spec.variable, spec.point)
    function = context.expr(spec.expression)
    if not function.is_polynomial(variable) or context.admissible_domain(variable) != sp.S.Reals or context.domain(spec.expression, variable) != sp.S.Reals:
        raise UnsupportedMath("Stationary classification currently requires a real polynomial on R")
    polynomial = sp.Poly(function, variable)
    if polynomial.degree() not in (2, 3) or any(c.is_real is not True or c.is_finite is not True for c in polynomial.all_coeffs()):
        raise UnsupportedMath("Only closed real quadratic/cubic stationary families are supported")
    first, second = (sp.simplify(sp.diff(function, variable, order).subs(variable, point)) for order in (1, 2))
    if first.is_zero is not True:
        raise UnsupportedMath("The requested point is not established stationary")
    if second.is_positive is True:
        return StationaryFacts(first, second, "local_minimum", "A real polynomial is smooth near the stationary point and its second derivative is strictly positive.")
    if second.is_negative is True:
        return StationaryFacts(first, second, "local_maximum", "A real polynomial is smooth near the stationary point and its second derivative is strictly negative.")
    if second.is_zero is True and polynomial.degree() == 3:
        h = sp.Dummy("h", positive=True)
        difference = sp.expand(function.subs(variable, point+h) - function.subs(variable, point))
        coefficient = sp.simplify(difference / h**3)
        if not coefficient.free_symbols and coefficient.is_nonzero is True:
            return StationaryFacts(first, second, "stationary_non_extremum",
                                   f"For every h>0, the increments are {coefficient}*h^3 and {-coefficient}*h^3; they have opposite signs. This independently disproves a local extremum.")
    raise UnsupportedMath("Local classification is not established by the supported polynomial facts")


@dataclass
class LimitFacts:
    status: str
    value: sp.Expr | None
    left: sp.Expr | None
    right: sp.Expr | None


def finite_limit(context: Context, spec: LimitSpec):
    variable, point = real_point(context, spec.variable, spec.point)
    expression = context.expr(spec.expression)
    if not expression.is_rational_function(variable):
        raise UnsupportedMath("Finite-point limit verification currently supports real rational functions only")
    domain = context.domain(spec.expression, variable) & context.admissible_domain(variable)
    punctured_neighborhood(domain, point, spec.direction)
    left = one_sided(expression, variable, point, "-") if spec.direction != "right" else None
    right = one_sided(expression, variable, point, "+") if spec.direction != "left" else None
    if left is not None and right is not None:
        equal = truth(sp.Eq(left, right))
        if equal is None:
            raise UnsupportedMath("Equality of one-sided limits is unresolved")
        if not equal:
            return LimitFacts("undefined", None, left, right)
    value = left if left is not None else right
    return LimitFacts("divergent" if value in (sp.oo, -sp.oo) else "numeric_value", value, left, right)


def affine_components(context, params):
    spec = context.problem.computation
    if not isinstance(spec, LimitSpec) or params.variable != spec.variable:
        raise UnsupportedMath("Quotient checks require the actual limit computation and variable")
    variable, point = real_point(context, spec.variable, spec.point)
    numerator, denominator = context.expr(params.numerator), context.expr(params.denominator)
    for expression in (numerator, denominator):
        if not expression.is_polynomial(variable):
            raise UnsupportedMath("The reviewed quotient rule currently requires affine components")
        polynomial = sp.Poly(expression, variable)
        if polynomial.degree() > 1 or any(c.is_real is not True or c.is_finite is not True for c in polynomial.all_coeffs()):
            raise UnsupportedMath("The actual quotient components must be affine with closed real coefficients")
    if denominator.is_zero is True or sp.simplify(context.expr(spec.expression) - numerator/denominator) != 0:
        raise UnsupportedMath("Declared quotient components do not match the actual limit expression")
    domain = context.domain(params.numerator, variable) & context.domain(params.denominator, variable)
    domain -= sp.solveset(denominator, variable, domain=sp.S.Reals)
    domain &= context.domain(spec.expression, variable) & context.admissible_domain(variable)
    punctured_neighborhood(domain, point, spec.direction)
    return numerator, denominator, variable, point


def lhopital_data(context, params):
    numerator, denominator, variable, point = affine_components(context, params)
    spec = context.problem.computation
    if spec.direction != "both" or context.expr(params.point) != point:
        raise UnsupportedMath("The reviewed zero-over-zero rule requires the actual two-sided finite point")
    derivative_denominator = sp.diff(denominator, variable)
    if derivative_denominator.is_nonzero is not True:
        raise UnsupportedMath("A nonzero denominator derivative on the punctured neighborhood was not established")
    form = numerator.subs(variable, point).is_zero is True and denominator.subs(variable, point).is_zero is True
    ratio = sp.simplify(sp.diff(numerator, variable) / derivative_denominator)
    return form, ratio
