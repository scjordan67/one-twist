"""Draft 17-20: independent mathematics only, no app/model/checker imports.

These direct SymPy calculations support the preimplementation review. They do
not establish runtime/API correctness or authorize publication.
"""

import pytest
import sympy as sp


@pytest.mark.parametrize(
    "p, factor_sum, principal, unchanged",
    [
        (1, sp.pi / 2, sp.pi / 2, True),
        (-1, 3 * sp.pi / 2, -sp.pi / 2, False),
        (2, sp.pi / 2, sp.pi / 2, True),
    ],
)
def test_17_principal_argument_matrix(p, factor_sum, principal, unchanged):
    z = sp.I * p
    assert z != 0
    actual_sum = sp.arg(sp.I) + sp.arg(sp.Integer(p))
    actual_principal = sp.arg(z)
    assert actual_sum == factor_sum
    assert actual_principal == principal
    assert bool(-sp.pi < actual_principal <= sp.pi)
    assert (actual_sum == actual_principal) is unchanged
    assert (actual_principal == sp.arg(sp.I)) is unchanged
    assert sp.simplify(
        (sp.cos(actual_principal) + sp.I * sp.sin(actual_principal) - z / sp.Abs(z)).doit()
    ) == 0
    if p == -1:
        assert actual_sum - actual_principal == 2 * sp.pi
        assert actual_sum > sp.pi


@pytest.mark.parametrize(
    "left, right, unwrapped, principal",
    [
        (-sp.I, -sp.I, -sp.pi, sp.pi),
        (sp.I, sp.I, sp.pi, sp.pi),
        (-sp.Integer(1), -sp.Integer(1), 2 * sp.pi, sp.Integer(0)),
        (-sp.Integer(1), sp.I, 3 * sp.pi / 2, -sp.pi / 2),
    ],
)
def test_17_branch_endpoints_and_winding(left, right, unwrapped, principal):
    assert sp.arg(left) + sp.arg(right) == unwrapped
    assert sp.arg(left * right) == principal
    assert bool(-sp.pi < principal <= sp.pi)
    assert sp.simplify((sp.exp(sp.I * unwrapped) - sp.exp(sp.I * principal)).doit()) == 0


def test_17_zero_has_no_principal_argument_and_negative_axis_uses_positive_pi():
    assert sp.arg(0) is sp.nan
    assert sp.arg(-1) == sp.pi
    assert sp.arg(-1) != -sp.pi


@pytest.mark.parametrize(
    "domain, expected",
    [
        (sp.S.Reals, sp.S.EmptySet),
        (sp.S.Complexes, sp.FiniteSet(-sp.I, sp.I)),
        (sp.Interval(0, sp.oo), sp.S.EmptySet),
    ],
)
def test_18_equation_domain_matrix(domain, expected):
    # A fresh unrestricted symbol avoids retaining a baseline real assumption.
    z = sp.Symbol("z")
    roots = sp.solveset(z**2 + 1, z, domain=domain)
    rearranged_roots = sp.solveset(sp.Eq(z**2, -1), z, domain=domain)
    assert roots == expected
    assert roots == rearranged_roots
    if isinstance(roots, sp.FiniteSet):
        assert all(sp.simplify((z**2 + 1).subs(z, root).doit()) == 0 for root in roots)
    baseline = sp.solveset(z**2 + 1, z, domain=sp.S.Reals)
    assert (roots != baseline) is (domain == sp.S.Complexes)


def test_18_complex_factorization_is_complete_and_real_square_extension_fails():
    z = sp.Symbol("z")
    x = sp.Symbol("x", real=True)
    assert sp.expand((z - sp.I) * (z + sp.I)) == z**2 + 1
    assert sp.Poly(z**2 + 1, z).degree() == 2
    assert len(sp.FiniteSet(-sp.I, sp.I)) == 2
    assert (x**2).is_nonnegative is True
    assert (sp.I**2).is_negative is True
    # Do not construct an ordering relation on a general complex symbol.
    assert sp.I**2 == -1


@pytest.mark.parametrize("a, expected", [(1, sp.pi / 4), (0, None), (2, sp.pi / 4)])
def test_19_vector_angle_matrix(a, expected):
    u, v = (sp.Integer(a), sp.Integer(0)), (sp.Integer(1), sp.Integer(1))
    dot = sum(left * right for left, right in zip(u, v, strict=True))
    norm_u_sq = sum(component**2 for component in u)
    norm_v_sq = sum(component**2 for component in v)
    assert (dot, norm_u_sq, norm_v_sq) == (a, a**2, 2)
    if a == 0:
        assert expected is None
        assert norm_u_sq == 0
        # The original vectors and metrics exist; division is deliberately not attempted.
        assert dot == 0 and norm_v_sq == 2
    else:
        ratio = dot / (sp.sqrt(norm_u_sq) * sp.sqrt(norm_v_sq))
        assert sp.sqrt(norm_u_sq) == abs(a)
        assert sp.simplify(ratio.doit()) == sp.sqrt(2) / 2
        assert bool(-1 <= ratio <= 1)
        assert sp.acos(ratio) == expected == sp.pi / 4


def test_19_negative_coefficient_requires_absolute_norm():
    a = sp.Integer(-1)
    ratio = a / (sp.sqrt(a**2) * sp.sqrt(2))
    assert ratio == -sp.sqrt(2) / 2
    assert sp.acos(ratio) == 3 * sp.pi / 4
    assert sp.sqrt(a**2) != a


@pytest.mark.parametrize(
    "u, v, expected",
    [
        ((1, 0, 0), (2, 0, 0), sp.Integer(0)),
        ((1, 0, 0), (-2, 0, 0), sp.pi),
        ((1, 0, 0), (0, 1, 0), sp.pi / 2),
    ],
)
def test_19_three_dimensional_angle_endpoints(u, v, expected):
    dot = sum(left * right for left, right in zip(u, v, strict=True))
    denominator = sp.sqrt(sum(component**2 for component in u)) * sp.sqrt(
        sum(component**2 for component in v)
    )
    assert denominator > 0
    assert sp.acos(dot / denominator) == expected


@pytest.mark.parametrize("u, v", [((0, 0), (1, 1)), ((1, 1), (0, 0)), ((0, 0), (0, 0))])
def test_19_zero_vector_identity_does_not_determine_an_angle(u, v):
    theta = sp.Symbol("theta", real=True)
    dot = sum(left * right for left, right in zip(u, v, strict=True))
    denominator = sp.sqrt(sum(component**2 for component in u)) * sp.sqrt(
        sum(component**2 for component in v)
    )
    assert denominator == dot == 0
    # 0 = 0 for every theta provides no unique angle.
    assert sp.simplify((dot - denominator * sp.cos(theta)).doit()) == 0


@pytest.mark.parametrize("c, b", [(0, 1), (1, 1), (0, 2)])
def test_20_all_coordinate_matrix(c, b):
    t, s = sp.symbols("t s", real=True)
    residuals = (t, -b * s, -sp.Integer(c))
    projected = sp.linsolve(residuals[:2], (t, s))
    full = sp.linsolve(residuals, (t, s))
    assert projected == sp.FiniteSet((0, 0))
    assert full == (sp.S.EmptySet if c else sp.FiniteSet((0, 0)))
    assert tuple(value.subs({t: 0, s: 0}) for value in residuals) == (0, 0, -c)
    d, e = (1, 0, 0), (0, b, 0)
    cross = (
        d[1] * e[2] - d[2] * e[1],
        d[2] * e[0] - d[0] * e[2],
        d[0] * e[1] - d[1] * e[0],
    )
    assert cross == (0, 0, b) != (0, 0, 0)
    assert sum(q * n for q, n in zip((0, 0, c), cross, strict=True)) == b * c
    # If c!=0: no intersection plus nonparallel directions establishes skew.
    assert bool(full is sp.S.EmptySet) is bool(c)


def test_20_control_is_only_a_reparameterization():
    s = sp.Symbol("s", real=True)
    control = (sp.Integer(0), 2 * s, sp.Integer(0))
    baseline_at_twice_s = (sp.Integer(0), 2 * s, sp.Integer(0))
    assert control == baseline_at_twice_s
    # r=2s is bijective on R: any baseline r is obtained by s=r/2.
    r = sp.Symbol("r", real=True)
    assert tuple(value.subs(s, r / 2) for value in control) == (0, r, 0)


def test_20_parallel_no_intersection_is_not_skew():
    t, s = sp.symbols("t s", real=True)
    # (t,0,0) and (2s,1,0): inconsistent y equation, parallel directions.
    assert sp.linsolve((t - 2 * s, -1, 0), (t, s)) is sp.S.EmptySet
    d, e = (1, 0, 0), (2, 0, 0)
    assert (
        d[1] * e[2] - d[2] * e[1],
        d[2] * e[0] - d[0] * e[2],
        d[0] * e[1] - d[1] * e[0],
    ) == (0, 0, 0)


def test_20_coincident_lines_have_no_unique_intersection():
    t, s = sp.symbols("t s", real=True)
    # Both are the x axis, with origins/parameter speeds changed.
    solution = sp.linsolve((t - 1 - 2 * s, 0, 0), (t, s))
    assert solution == sp.FiniteSet((1 + 2 * s, s))
    assert solution.free_symbols == {s}


def test_20_zero_direction_is_a_point_and_not_a_line():
    t = sp.Symbol("t", real=True)
    origin, direction = (1, 2, 3), (0, 0, 0)
    assert sum(component**2 for component in direction) == 0
    assert tuple(p + t * d for p, d in zip(origin, direction, strict=True)) == origin
