"""The reviewed reciprocal-affine and two-coalescing-pole families only."""
from dataclasses import dataclass

import sympy as sp

from app.engine.context import Context, UnsupportedMath, subset
from app.models.domain import IntegralSpec


def actual_integral(context: Context):
    spec = context.problem.computation
    if not isinstance(spec, IntegralSpec):
        raise UnsupportedMath("An actual integral computation is required")
    return spec, context.symbols[spec.variable], context.expr(spec.integrand)


def simple_pole(context: Context):
    spec, x, integrand = actual_integral(context)
    # Recognize exactly 1/(x-c), not arbitrary rational singularities.
    reciprocal = sp.cancel(1/integrand)
    polynomial = sp.Poly(reciprocal, x)
    if polynomial.degree() != 1 or polynomial.LC() != 1:
        raise UnsupportedMath("Interior splitting only supports the reviewed 1/(x-c) family")
    pole = -polynomial.nth(0)
    if pole.free_symbols or pole.is_real is not True or pole.is_finite is not True:
        raise UnsupportedMath("The simple pole must have an established finite real location")
    if context.domain(spec.integrand, x) != sp.S.Reals-sp.FiniteSet(pole):
        raise UnsupportedMath("Additional retained integrand restrictions are unsupported for splitting")
    return spec, x, pole


def component_primitive(context: Context, primitive):
    spec, x, pole = simple_pole(context)
    # A sign on each connected component removes Abs before differentiation.
    raw = context.expr(primitive)
    h = sp.Dummy("distance_from_pole", positive=True)
    for sign in (-1, 1):
        restricted = sp.simplify(raw.subs(x, pole+sign*h).doit())
        if sp.simplify((sign*sp.diff(restricted, h)-1/(sign*h)).doit()) != 0:
            return False
    return context.domain(primitive, x) == sp.S.Reals-sp.FiniteSet(pole)


def interior_contributions(context: Context):
    spec, x, pole = simple_pole(context)
    lower, upper = context.expr(spec.lower), context.expr(spec.upper)
    if not (lower < pole < upper):
        raise UnsupportedMath("Reviewed interior splitting requires increasing bounds around the pole")
    allowed = sp.Interval(lower, upper)-sp.FiniteSet(pole)
    for predicate in context.constraints(x):
        if subset(allowed, context.constraint_set(predicate, x)) is not True:
            raise UnsupportedMath("Additional interval restrictions need a separate proof")
    left_cutoff, right_cutoff = sp.symbols("left_cutoff right_cutoff", positive=True)
    # Integrate on two separate regular intervals, never tie their cutoffs.
    left = sp.log(left_cutoff)-sp.log(pole-lower)
    right = sp.log(upper-pole)-sp.log(right_cutoff)
    return (sp.limit(left, left_cutoff, 0, dir="+"),
            sp.limit(right, right_cutoff, 0, dir="+"))


@dataclass
class TwoPoleFacts:
    x: sp.Symbol
    a: sp.Expr
    integrand: sp.Expr
    solvable: bool
    rank: int
    augmented_rank: int
    repair_verified: bool


def two_pole_facts(context: Context) -> TwoPoleFacts:
    spec, x, integrand = actual_integral(context)
    polynomial = sp.Poly(sp.cancel(1/integrand), x)
    if polynomial.degree() != 2 or polynomial.LC() != 1 or polynomial.nth(0) != 0:
        raise UnsupportedMath("Expected the actual 1/[x(x-a)] family")
    a = sp.simplify((-polynomial.nth(1)).doit())
    if a.free_symbols or a.is_real is not True or a.is_finite is not True:
        raise UnsupportedMath("Pole separation must be a closed finite real value")
    expected_domain = sp.S.Reals-sp.FiniteSet(0, a)
    if context.domain(spec.integrand, x) != expected_domain:
        raise UnsupportedMath("Extra retained integrand restrictions need separate analysis")
    interval = context.interval(spec)
    if subset(interval, expected_domain) is not True:
        raise UnsupportedMath("The reviewed coalescing-pole integral must remain proper")
    for predicate in context.constraints(x):
        if subset(interval, context.constraint_set(predicate, x)) is not True:
            raise UnsupportedMath("Integral constraints are not established on the whole interval")
    matrix = sp.Matrix([[1, 1], [-a, 0]]).applyfunc(lambda value: sp.simplify(value.doit()))
    target = sp.Matrix([0, 1])
    rank, augmented = matrix.rank(), matrix.row_join(target).rank()
    repair = False
    if a == 0:
        repeated = 0/x+1/x**2
        primitive = -1/x
        repair = (sp.simplify((repeated-integrand).doit()) == 0 and
                  sp.simplify((sp.diff(primitive, x)-integrand).doit()) == 0)
    return TwoPoleFacts(x, a, integrand, rank == augmented, rank, augmented, repair)
