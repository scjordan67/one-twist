"""Worker-only expression construction and real-domain bookkeeping."""

import sympy as sp
from sympy.calculus.util import continuous_domain

from app.core.parsing import parse_math
from app.models.domain import MathExpression, Predicate, Problem


class UnsupportedMath(ValueError):
    """The finite rule set cannot establish this fact."""


def math_expression(value: sp.Basic) -> MathExpression:
    # Output source is optional: sets and generated expressions are not input
    # to the restricted grammar. LaTeX is generated from the computed object.
    return MathExpression(latex=sp.latex(value))


def truth(value) -> bool | None:
    if value is True or value is sp.S.true:
        return True
    if value is False or value is sp.S.false:
        return False
    return None


def subset(left: sp.Set, right: sp.Set) -> bool | None:
    # SymPy is_subset can return None even for [0,1] versus R\{1}.
    # A simplified difference often supplies the missing definitive witness.
    empty = truth((left - right).is_empty)
    return empty if empty is not None else truth(left.is_subset(right))


def equal_sets(left: sp.Set, right: sp.Set) -> bool | None:
    return truth((left.symmetric_difference(right)).is_empty)


class Context:
    def __init__(self, problem: Problem):
        self.problem = problem
        domains = dict(problem.variables)
        domains.update({item.name: item.domain for item in problem.parameters})
        self.symbols = {name: sp.Symbol(name, **{domain: True}) for name, domain in domains.items()}
        self.values = {}
        for parameter in problem.parameters:
            if self.definedness(parameter.value, "complex" if parameter.domain == "complex" else "real") is not True:
                raise UnsupportedMath("Parameter construction is not established defined in its declared domain")
            value = sp.simplify(self.parse(parameter.value).doit())
            if value.free_symbols or value.is_finite is not True:
                raise UnsupportedMath("Parameter must be a finite constant")
            if parameter.domain == "real" and value.is_real is not True:
                raise UnsupportedMath("Parameter is not established real")
            if parameter.domain == "integer" and value.is_integer is not True:
                raise UnsupportedMath("Parameter is not established integer")
            self.values[self.symbols[parameter.name]] = value

    def parse(self, expression: MathExpression) -> sp.Expr:
        if expression.source is None:
            raise UnsupportedMath("A computational expression has no source")
        return parse_math(expression.source, symbols=self.symbols)

    def raw(self, expression: MathExpression) -> sp.Expr:
        def replace(node):
            if node in self.values:
                return self.values[node]
            if not node.args:
                return node
            return node.func(*(replace(arg) for arg in node.args), evaluate=False)
        return replace(self.parse(expression))

    def expr(self, expression: MathExpression) -> sp.Expr:
        # Retained syntax is deliberately noncanonical. SymPy's assumption
        # handlers used by simplify assume evaluated arithmetic: for example,
        # an unevaluated -1*0 can yield contradictory odd/even facts. Evaluate
        # a computation copy first; domain/definedness checks still use raw().
        return sp.simplify(self.raw(expression).doit())

    def definedness(self, expression: MathExpression, value_domain: str = "real") -> bool | None:
        """Check each unevaluated intermediate before allowing simplification."""
        raw = self.raw(expression)
        if raw.free_symbols:
            return None
        unknown = False
        for node in sp.postorder_traversal(raw):
            if isinstance(node, sp.Pow) and node.base.is_zero is True and node.exp.is_zero is True:
                raise UnsupportedMath("Zero-to-zero power conventions are not supported")
            finite = node.is_finite
            real = node.is_real if value_domain == "real" else True
            if finite is False or real is False or node in (sp.nan, sp.zoo, sp.oo, -sp.oo):
                return False
            unknown |= finite is None or real is None
        return None if unknown else True

    def constraints(self, variable: sp.Symbol) -> list[Predicate]:
        return [*self.problem.domain_constraints, *(
            predicate for condition in self.problem.conditions
            if condition.domain_binding is not None and condition.domain_binding.variable == str(variable)
            for predicate in condition.domain_binding.current.constraints
        )]

    def admissible_domain(self, variable: sp.Symbol) -> sp.Set:
        number_system = self.problem.variables[str(variable)]
        if number_system == "complex":
            raise UnsupportedMath("Complex equation domains are not supported yet")
        result = sp.S.Integers if number_system == "integer" else sp.S.Reals
        for predicate in self.constraints(variable):
            result &= self.constraint_set(predicate, variable)
        return result

    def predicate(self, predicate: Predicate):
        left, right = self.expr(predicate.left), self.expr(predicate.right)
        if any(value.has(sp.nan, sp.zoo, sp.oo, -sp.oo) for value in (left, right)):
            raise UnsupportedMath("Predicate contains an undefined or non-finite expression")
        relation = {"eq": sp.Eq, "ne": sp.Ne, "lt": sp.Lt, "le": sp.Le, "gt": sp.Gt, "ge": sp.Ge}[predicate.relation]
        return relation(left, right)

    def constraint_set(self, predicate: Predicate, variable: sp.Symbol) -> sp.Set:
        domain = self.domain(predicate.left, variable) & self.domain(predicate.right, variable)
        relation = self.predicate(predicate)
        known = truth(relation)
        if known is not None:
            return domain if known else sp.S.EmptySet
        if relation.free_symbols - {variable}:
            raise UnsupportedMath("Constraint depends on an unresolved variable")
        result = relation.as_set()
        if result.has(sp.ConditionSet):
            raise UnsupportedMath("Constraint remains conditional")
        return result & domain

    def domain(self, expression: MathExpression, variable: sp.Symbol) -> sp.Set:
        raw = self.raw(expression)
        if raw.free_symbols - {variable}:
            raise UnsupportedMath("Expression depends on an unresolved variable")
        result = continuous_domain(raw, variable, sp.S.Reals)
        # Retain syntactic denominator restrictions even if the expression
        # cancels later (x/x -> 1). Work on the unevaluated tree.
        for node in sp.preorder_traversal(raw):
            if isinstance(node, sp.Pow) and node.exp.is_negative is True:
                zeros = sp.solveset(node.base, variable, domain=sp.S.Reals)
                if zeros.has(sp.ConditionSet):
                    raise UnsupportedMath("Denominator zeros remain conditional")
                result -= zeros
        return result

    def interval(self, spec) -> sp.Interval:
        lower, upper = self.expr(spec.lower), self.expr(spec.upper)
        if lower.is_real is not True or upper.is_real is not True or lower.is_finite is not True or upper.is_finite is not True:
            raise UnsupportedMath("Only finite real bounds are supported")
        if truth(lower <= upper) is True:
            return sp.Interval(lower, upper)
        if truth(upper <= lower) is True:
            return sp.Interval(upper, lower)
        raise UnsupportedMath("Cannot order interval bounds")
