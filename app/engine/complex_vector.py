"""Finite complex-argument, vector and 3D line facts; worker-only, no new CAS."""
from dataclasses import dataclass

import sympy as sp

from app.engine.context import Context, UnsupportedMath, truth
from app.models.domain import (
    LineIntersection3DSpec, MathExpression, PrincipalArgumentSpec, VectorAngleSpec,
)


def principal_argument_value(context: Context, expression: MathExpression) -> sp.Expr | None:
    """Return the principal Arg in (-pi, pi], or None if the input is zero."""
    if context.definedness(expression, "complex") is not True:
        raise UnsupportedMath("Argument input is not established defined")
    value = context.expr(expression)
    is_zero = value.is_zero
    if is_zero is None:
        raise UnsupportedMath("Zero test for the argument input is unresolved")
    if is_zero:
        return None
    theta = sp.arg(value)
    if theta.is_real is not True or theta.is_finite is not True:
        raise UnsupportedMath("Principal argument is not established real and finite")
    lower = truth(theta > -sp.pi)
    upper = truth(theta <= sp.pi)
    if lower is None or upper is None:
        raise UnsupportedMath("Principal branch membership is unresolved")
    if not (lower and upper):
        raise UnsupportedMath("Computed argument is outside the declared branch")
    return theta


def principal_argument_facts(context: Context, spec: PrincipalArgumentSpec) -> sp.Expr | None:
    return principal_argument_value(context, spec.expression)


@dataclass
class ArgumentAdditivity:
    alpha: sp.Expr
    beta: sp.Expr
    unwrapped: sp.Expr
    principal: sp.Expr
    additive: bool


def argument_additivity_data(context: Context, params) -> ArgumentAdditivity:
    spec = context.problem.computation
    if not isinstance(spec, PrincipalArgumentSpec):
        raise UnsupportedMath("Argument additivity must reference the actual principal-argument computation")
    if context.definedness(params.left, "complex") is not True or context.definedness(params.right, "complex") is not True:
        raise UnsupportedMath("Both factors must be established defined")
    left, right = context.expr(params.left), context.expr(params.right)
    if left.is_zero is not False or right.is_zero is not False:
        raise UnsupportedMath("Both factors must be established nonzero")
    product = context.expr(spec.expression)
    if sp.simplify(product - left * right) != 0:
        raise UnsupportedMath("Declared factors do not match the actual expression")
    alpha, beta = sp.arg(left), sp.arg(right)
    if any(item.is_real is not True or item.is_finite is not True for item in (alpha, beta)):
        raise UnsupportedMath("Factor principal arguments are not established real and finite")
    unwrapped = sp.simplify(alpha + beta)
    principal = principal_argument_value(context, spec.expression)
    if principal is None:
        raise UnsupportedMath("Product argument is undefined")
    lower = truth(unwrapped > -sp.pi)
    upper = truth(unwrapped <= sp.pi)
    if lower is None or upper is None:
        raise UnsupportedMath("Branch membership of the unwrapped sum is unresolved")
    return ArgumentAdditivity(alpha, beta, unwrapped, principal, bool(lower and upper))


@dataclass
class VectorFacts:
    dot: sp.Expr
    norm_u_sq: sp.Expr
    norm_v_sq: sp.Expr
    angle: sp.Expr | None


def _closed_real_vector(context: Context, vector) -> list[sp.Expr]:
    values = []
    for component in vector:
        if context.definedness(component, "real") is not True:
            raise UnsupportedMath("A vector component is not established real and finite")
        values.append(context.expr(component))
    return values


def vector_angle_facts(context: Context, spec: VectorAngleSpec) -> VectorFacts:
    if len(spec.u) != len(spec.v):
        raise UnsupportedMath("Vectors must share a dimension")
    u, v = _closed_real_vector(context, spec.u), _closed_real_vector(context, spec.v)
    dot = sp.simplify(sum(a * b for a, b in zip(u, v, strict=True)))
    norm_u_sq = sp.simplify(sum(a * a for a in u))
    norm_v_sq = sp.simplify(sum(b * b for b in v))
    zero_u, zero_v = norm_u_sq.is_zero, norm_v_sq.is_zero
    if zero_u is None or zero_v is None:
        raise UnsupportedMath("Zero-norm test is unresolved")
    if zero_u or zero_v:
        return VectorFacts(dot, norm_u_sq, norm_v_sq, None)
    ratio = sp.simplify(dot / (sp.sqrt(norm_u_sq) * sp.sqrt(norm_v_sq)))
    in_range = truth(sp.And(ratio >= -1, ratio <= 1))
    if in_range is None:
        raise UnsupportedMath("Cauchy-Schwarz ratio range is unresolved")
    if not in_range:
        raise UnsupportedMath("Computed ratio is outside the valid cosine range")
    angle = sp.acos(ratio)
    if angle.is_real is not True or angle.is_finite is not True:
        raise UnsupportedMath("Vector angle is not established real and finite")
    return VectorFacts(dot, norm_u_sq, norm_v_sq, angle)


LineRelation = str  # "intersecting" | "skew" | "parallel_distinct" | "coincident"


@dataclass
class LineFacts:
    relation: LineRelation
    point: tuple[sp.Expr, sp.Expr, sp.Expr] | None
    direction_cross: tuple[sp.Expr, sp.Expr, sp.Expr]


def _cross(d, e):
    return (d[1] * e[2] - d[2] * e[1], d[2] * e[0] - d[0] * e[2], d[0] * e[1] - d[1] * e[0])


def line_intersection_facts(context: Context, spec: LineIntersection3DSpec) -> LineFacts:
    origin1, direction1 = _closed_real_vector(context, spec.first.origin), _closed_real_vector(context, spec.first.direction)
    origin2, direction2 = _closed_real_vector(context, spec.second.origin), _closed_real_vector(context, spec.second.direction)
    for direction in (direction1, direction2):
        nonzero = sp.simplify(sum(c * c for c in direction)).is_zero
        if nonzero is None:
            raise UnsupportedMath("Zero-direction test is unresolved")
        if nonzero:
            raise UnsupportedMath("A zero direction is not a line")
    t, s = sp.Dummy("t", real=True), sp.Dummy("s", real=True)
    residuals = [
        sp.simplify(origin1[i] + t * direction1[i] - origin2[i] - s * direction2[i])
        for i in range(3)
    ]
    solution = sp.linsolve(residuals, (t, s))
    cross = _cross(direction1, direction2)
    parallel = sp.simplify(sum(c * c for c in cross)).is_zero
    if parallel is None:
        raise UnsupportedMath("Direction-parallelism test is unresolved")
    if isinstance(solution, sp.FiniteSet) and len(solution) == 1:
        (t_value, s_value), = solution
        if t_value.free_symbols or s_value.free_symbols:
            # linsolve represents an underdetermined (one-parameter) family as
            # a single tuple containing a free symbol, not a concrete point.
            if not parallel:
                raise UnsupportedMath("A free-parameter solution without parallel directions is inconsistent")
            return LineFacts("coincident", None, cross)
        point1 = tuple(sp.simplify(origin1[i] + t_value * direction1[i]) for i in range(3))
        point2 = tuple(sp.simplify(origin2[i] + s_value * direction2[i]) for i in range(3))
        if any(sp.simplify(a - b) != 0 for a, b in zip(point1, point2, strict=True)):
            raise UnsupportedMath("Unique parameter solution does not reproduce a common point")
        if parallel:
            raise UnsupportedMath("A unique parameter solution with parallel directions is inconsistent")
        return LineFacts("intersecting", point1, cross)
    if solution is sp.S.EmptySet or (hasattr(solution, "is_empty") and solution.is_empty is True):
        if parallel:
            return LineFacts("parallel_distinct", None, cross)
        return LineFacts("skew", None, cross)
    if parallel:
        return LineFacts("coincident", None, cross)
    raise UnsupportedMath("The component system did not resolve to a supported relation")
