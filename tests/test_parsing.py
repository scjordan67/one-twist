import builtins
import os

import pytest
import sympy as sp

from app.core.parsing import (
    MAX_DEPTH, MAX_DIGITS, MAX_EXPONENT, MAX_LENGTH, MathSyntaxError, parse_math,
)


@pytest.mark.parametrize("source,expected", [
    ("2+3*4", sp.Integer(14)), ("0.125", sp.Rational(1, 8)),
    ("1/3", sp.Rational(1, 3)), ("-2", sp.Integer(-2)),
    ("+2", sp.Integer(2)), ("2**-3", sp.Rational(1, 8)),
    ("sqrt(4)", sp.Integer(2)), ("sin(pi/2)", sp.Integer(1)),
    ("cos(0)", sp.Integer(1)), ("tan(0)", sp.Integer(0)),
    ("log(E)", sp.Integer(1)), ("exp(0)", sp.Integer(1)),
    ("abs(-2)", sp.Integer(2)), ("I**2", sp.Integer(-1)),
])
def test_supported_arithmetic(source, expected):
    assert sp.simplify(parse_math(source)) == expected


def test_declared_symbols_and_exact_decimal():
    x = sp.Symbol("x")
    assert sp.simplify(parse_math("(x+0.1)/2", symbols={"x"}) - (x + sp.Rational(1, 10))/2) == 0


def test_domain_sensitive_structure_is_not_cancelled():
    expr = parse_math("x/x", symbols={"x"})
    assert expr != sp.Integer(1)
    assert expr.has(sp.Pow(sp.Symbol("x"), -1))
    # Parsing does not judge the definedness of a zero denominator.
    assert parse_math("1/0").has(sp.Pow(0, -1, evaluate=False))


@pytest.mark.parametrize("source", [
    "", " ", "z", "x.__class__", "(1).__class__", "x[0]",
    "__import__('os').system('echo unsafe')", "open('file','w')", "eval('1')",
    "exec('x=1')", "lambda: 1", "[x for x in (1,2)]", "{'x':1}",
    "(1,2)", "[1]", "True", "None", "'1'", "1;2", "1\n+2",
    "1 # comment", "sin(x=1)", "sin(1,2)", "sin(*x)", "sin(**x)",
    "factorial(5)", "sin", "sqrt()", "2^3", "2//3", "2%3", "1<2",
    "2x", "1e100", "0xFF", "1_000", "1j", "π", "x**x",
    "x**(1/2)", "2**(2**3)", "(x:=1)", "(1)(2)",
])
def test_unsupported_syntax_is_rejected(source):
    with pytest.raises(MathSyntaxError):
        parse_math(source, symbols={"x"})


@pytest.mark.parametrize("source,match", [
    ("1" * (MAX_LENGTH + 1), "length"),
    ("1" * (MAX_DIGITS + 1), "digit"),
    ("(" * (MAX_DEPTH + 1) + "1" + ")" * (MAX_DEPTH + 1), "nesting"),
    ("x**" + str(MAX_EXPONENT + 1), "Exponent"),
    ("x**-" + str(MAX_EXPONENT + 1), "Exponent"),
    ("+" * (MAX_DEPTH + 1) + "1", "depth"),
    ("+".join(["1"] * 50), "node"),
])
def test_complexity_budgets(source, match):
    with pytest.raises(MathSyntaxError, match=match):
        parse_math(source, symbols={"x"})


def test_inclusive_limits_are_accepted():
    assert parse_math("1" * MAX_DIGITS) == sp.Integer("1" * MAX_DIGITS)
    assert parse_math("(" * MAX_DEPTH + "1" + ")" * MAX_DEPTH) == 1
    assert parse_math("x**16", symbols={"x"}).exp == MAX_EXPONENT
    assert parse_math("x**-16", symbols={"x"}).exp == -MAX_EXPONENT


@pytest.mark.parametrize("names", [{"__class__"}, {"sin"}, {"pi"}, {"a.b"}, {f"x{i}" for i in range(33)}])
def test_invalid_symbol_declarations(names):
    with pytest.raises(MathSyntaxError, match="symbol name"):
        parse_math("1", symbols=names)


def test_input_never_reaches_python_execution(monkeypatch, tmp_path):
    sentinel = tmp_path / "should-not-exist"
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(args)
        raise AssertionError("Python input execution was attempted")

    with monkeypatch.context() as patch:
        patch.setattr(builtins, "eval", forbidden)
        patch.setattr(builtins, "exec", forbidden)
        patch.setattr(os, "system", forbidden)
        assert parse_math("x/x", symbols={"x"}).has(sp.Symbol("x"))
        for payload in [
            f"open({str(sentinel)!r}, 'w')",
            "__import__('os').system('echo unsafe')", "eval('1+1')",
        ]:
            with pytest.raises(MathSyntaxError):
                parse_math(payload)
    assert not calls
    assert not sentinel.exists()


def test_entire_tree_is_validated_before_sympy_construction(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Started constructing an invalid tree")

    monkeypatch.setattr(sp, "Rational", forbidden)
    with pytest.raises(MathSyntaxError):
        parse_math("1+unknown(2)")
