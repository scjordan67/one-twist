"""Bounded arithmetic grammar; no eval, exec, sympify or parse_expr on input.

Construction deliberately preserves unevaluated operations and domain-sensitive
syntax. Parsing is not a mathematical validity check or a compute sandbox.
"""

import ast
import io
import re
import tokenize
from collections.abc import Iterable, Mapping

import sympy as sp

MAX_LENGTH = 1024
MAX_DEPTH = 24
MAX_NODES = 128
MAX_DIGITS = 32
MAX_EXPONENT = 16
MAX_SYMBOLS = 32

_NUMBER = re.compile(r"[0-9]+(?:\.[0-9]+)?\Z")
_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]*\Z")
_FUNCTIONS = {
    "sin": sp.sin, "cos": sp.cos, "tan": sp.tan,
    "exp": sp.exp, "log": sp.log, "abs": sp.Abs,
}
_CONSTANTS = {"pi": sp.pi, "E": sp.E, "I": sp.I}


class MathSyntaxError(ValueError):
    """Input is outside the supported grammar or its resource budget."""


def _check_tokens(source: str) -> None:
    depth = 0
    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.NUMBER:
                if not _NUMBER.fullmatch(token.string):
                    raise MathSyntaxError("Only integer and decimal literals are supported")
                if sum(char.isdigit() for char in token.string) > MAX_DIGITS:
                    raise MathSyntaxError("Numeric literal exceeds digit limit")
            elif token.type == tokenize.OP:
                if token.string not in {"+", "-", "*", "/", "**", "(", ")"}:
                    raise MathSyntaxError("Unsupported operator")
                if token.string == "(":
                    depth += 1
                    if depth > MAX_DEPTH:
                        raise MathSyntaxError("Expression exceeds nesting limit")
                elif token.string == ")":
                    depth -= 1
            elif token.type not in {
                tokenize.NAME, tokenize.NEWLINE, tokenize.ENDMARKER,
            }:
                raise MathSyntaxError("Unsupported token")
    except (tokenize.TokenError, IndentationError) as exc:
        raise MathSyntaxError("Malformed expression") from exc


def _literal_exponent(node: ast.AST) -> int:
    sign = 1
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        sign = -1 if isinstance(node.op, ast.USub) else 1
        node = node.operand
    if not isinstance(node, ast.Constant) or type(node.value) is not int:
        raise MathSyntaxError("Exponent must be a literal integer")
    if abs(node.value) > MAX_EXPONENT:
        raise MathSyntaxError("Exponent exceeds limit")
    return sign * node.value


def parse_math(source: str, *, symbols: Iterable[str] | Mapping[str, sp.Symbol] = ()) -> sp.Expr:
    """Accept + - * / **, literal integer powers and unary math functions.

    Numbers are exact. Decimal literals become Rational objects. Attributes,
    indexing, implicit multiplication, keyword arguments and Python code are
    rejected. Integral/Limit/equation notation remains display-only in Phase 1.
    """
    if not source or len(source) > MAX_LENGTH:
        raise MathSyntaxError("Expression is empty or exceeds length limit")
    if not source.isascii() or "\n" in source or "\r" in source:
        raise MathSyntaxError("Use a single line of ASCII mathematical syntax")
    names = set(symbols)
    reserved = set(_FUNCTIONS) | set(_CONSTANTS) | {"sqrt"}
    if len(names) > MAX_SYMBOLS or any(
        not _NAME.fullmatch(name) or name in reserved for name in names
    ):
        raise MathSyntaxError("Invalid or reserved symbol name")
    source = source.strip()
    _check_tokens(source)
    try:
        tree = ast.parse(source, mode="eval")
    except (SyntaxError, ValueError, RecursionError) as exc:
        raise MathSyntaxError("Malformed expression") from exc
    if sum(1 for _ in ast.walk(tree)) > MAX_NODES:
        raise MathSyntaxError("Expression exceeds node limit")

    def validate(node: ast.AST, depth: int = 0) -> None:
        if depth > MAX_DEPTH:
            raise MathSyntaxError("Expression exceeds tree depth limit")
        if isinstance(node, ast.Constant):
            if type(node.value) not in (int, float):
                raise MathSyntaxError("Only numeric literals are supported")
        elif isinstance(node, ast.Name):
            if node.id not in names and node.id not in _CONSTANTS:
                raise MathSyntaxError(f"Undeclared symbol: {node.id}")
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            validate(node.operand, depth + 1)
        elif isinstance(node, ast.BinOp) and isinstance(
            node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)
        ):
            if isinstance(node.op, ast.Pow):
                _literal_exponent(node.right)
            validate(node.left, depth + 1)
            validate(node.right, depth + 1)
        elif isinstance(node, ast.Call):
            if (
                not isinstance(node.func, ast.Name)
                or node.func.id not in set(_FUNCTIONS) | {"sqrt"}
                or len(node.args) != 1 or node.keywords
            ):
                raise MathSyntaxError("Only whitelisted unary math functions are allowed")
            validate(node.args[0], depth + 1)
        else:
            raise MathSyntaxError("Unsupported syntax node")

    validate(tree.body)
    symbol_objects = dict(symbols) if isinstance(symbols, Mapping) else {name: sp.Symbol(name) for name in names}

    def construct(node: ast.AST) -> sp.Expr:
        if isinstance(node, ast.Constant):
            return sp.Rational(ast.get_source_segment(source, node))
        if isinstance(node, ast.Name):
            return symbol_objects[node.id] if node.id in symbol_objects else _CONSTANTS[node.id]
        if isinstance(node, ast.UnaryOp):
            value = construct(node.operand)
            return sp.Mul(-1, value, evaluate=False) if isinstance(node.op, ast.USub) else value
        if isinstance(node, ast.Call):
            value = construct(node.args[0])
            if node.func.id == "sqrt":
                return sp.Pow(value, sp.Rational(1, 2), evaluate=False)
            return _FUNCTIONS[node.func.id](value, evaluate=False)
        left = construct(node.left)
        if isinstance(node.op, ast.Pow):
            return sp.Pow(left, _literal_exponent(node.right), evaluate=False)
        right = construct(node.right)
        if isinstance(node.op, ast.Add):
            return sp.Add(left, right, evaluate=False)
        if isinstance(node.op, ast.Sub):
            return sp.Add(left, sp.Mul(-1, right, evaluate=False), evaluate=False)
        if isinstance(node.op, ast.Mult):
            return sp.Mul(left, right, evaluate=False)
        return sp.Mul(left, sp.Pow(right, -1, evaluate=False), evaluate=False)

    return construct(tree.body)
