"""Proofs for the two reviewed IVP families, never a general ODE solver."""
from dataclasses import dataclass

import sympy as sp
from sympy.calculus.util import continuous_domain

from app.engine.context import Context, UnsupportedMath, subset, truth
from app.models.domain import FirstOrderIVPSpec


@dataclass
class IVPFacts:
    spec: FirstOrderIVPSpec
    t: sp.Symbol
    y: sp.Symbol
    initial: sp.Expr
    domain: sp.Set
    family: str
    reference: sp.Expr
    proof: str


def ivp_facts(context: Context) -> IVPFacts:
    spec = context.problem.computation
    if not isinstance(spec, FirstOrderIVPSpec):
        raise UnsupportedMath("An actual IVP computation is required")
    t, y = context.symbols[spec.independent_variable], context.symbols[spec.dependent_variable]
    initial_time, initial = context.expr(spec.initial_time), context.expr(spec.initial_value)
    if initial_time != 0 or initial.free_symbols or initial.is_real is not True or initial.is_finite is not True:
        raise UnsupportedMath("Reviewed IVPs require time zero and a closed finite real initial value")
    if context.problem.domain_constraints or any(item.domain_binding for item in context.problem.conditions):
        raise UnsupportedMath("Additional IVP constraints require a separate proof")
    if spec.state_domain.number_system != "real":
        raise UnsupportedMath("Only real state domains are supported")
    time = spec.time_domain
    lower = context.expr(time.lower) if time.lower else -sp.oo
    upper = context.expr(time.upper) if time.upper else sp.oo
    if any(item.free_symbols or item.is_extended_real is not True for item in (lower, upper)):
        raise UnsupportedMath("Time bounds must be closed real constants")
    domain = sp.Interval(lower, upper, left_open=not time.left_closed, right_open=not time.right_closed)
    if truth(domain.contains(initial_time)) is not True:
        raise UnsupportedMath("Initial time must belong to the declared time domain")
    rhs = context.expr(spec.rhs)
    if context.domain(spec.rhs, y) != continuous_domain(rhs, y, sp.S.Reals):
        raise UnsupportedMath("A cancelled RHS restriction needs a separate proof")
    if rhs == y:
        if spec.state_domain.constraints or domain != sp.S.Reals:
            raise UnsupportedMath("The reviewed linear IVP uses the unrestricted real time/state domains")
        reference = initial*sp.exp(t)
        # Identity for an arbitrary differentiable solution, not just a candidate.
        Y = sp.Function("Y")(t)
        identity = sp.diff(sp.exp(-t)*Y, t)-sp.exp(-t)*(sp.diff(Y, t)-Y)
        if sp.simplify(identity.doit()) != 0:
            raise UnsupportedMath("Integrating-factor identity was not established")
        return IVPFacts(spec, t, y, initial, domain, "linear", reference,
                        "(exp(-t)*y)'=exp(-t)*(y'-y)=0 for every solution on R; its constant is fixed by y(0).")
    if rhs == 2*sp.sqrt(y):
        state = sp.S.Reals
        for predicate in spec.state_domain.constraints:
            state &= context.constraint_set(predicate, y)
        if domain != sp.Interval(0, sp.oo) or state != sp.Interval(0, sp.oo):
            raise UnsupportedMath("The square-root family requires forward time and nonnegative state")
        # A single static template declares one of these two supported scopes;
        # perturbing the initial state can cross from one actual family to the
        # other, so the ESTABLISHED family (and the scope the engine reports)
        # is read from the computed initial value, never trusted from this field.
        if spec.solution_scope not in ("verified_witness", "nonuniqueness_witnesses"):
            raise UnsupportedMath("This batch verifies positive-initial-state witnesses or disproves uniqueness at a zero state")
        if initial.is_zero is True:
            return IVPFacts(spec, t, y, initial, domain, "sqrt_zero", None,
                            "The RHS 2*sqrt(y) is not Lipschitz at y=0 (1/sqrt(y) is unbounded there). This alone is "
                            "not a nonuniqueness proof; two verified, pairwise distinct solutions establish it instead, "
                            "without claiming they exhaust every solution.")
        if initial.is_positive is not True:
            raise UnsupportedMath("This batch verifies positive-initial-state witnesses, not square-root uniqueness")
        return IVPFacts(spec, t, y, initial, domain, "sqrt", (t+sp.sqrt(initial))**2,
                        "The nonnegative RHS makes every forward solution nondecreasing from its positive initial state; u=sqrt(y)>0.")
    raise UnsupportedMath("Actual RHS is outside the two reviewed IVP families")


def candidate_valid(context: Context, facts: IVPFacts, expression) -> tuple[bool, sp.Expr, str]:
    candidate = context.expr(expression)
    t = facts.t
    if candidate.free_symbols - {t}:
        raise UnsupportedMath("IVP candidate depends on an unresolved state or auxiliary symbol")
    if subset(facts.domain, context.domain(expression, t)) is not True:
        raise UnsupportedMath("Candidate definedness on the entire time domain is not established")
    if sp.simplify((candidate.subs(t, 0)-facts.initial).doit()) != 0:
        return False, candidate, "Candidate does not satisfy the initial value."
    if facts.family == "linear":
        derivative = sp.diff(candidate, t)
        if subset(facts.domain, continuous_domain(derivative, t, sp.S.Reals)) is not True:
            raise UnsupportedMath("C1 regularity on the complete time domain is unresolved")
        residual = sp.simplify((derivative-candidate).doit())
        if residual != 0:
            if residual.is_zero is None:
                raise UnsupportedMath("Candidate residual remains unresolved")
            return False, candidate, f"Candidate has nonzero ODE residual {residual}."
    elif facts.family == "sqrt_zero":
        # No (t+C)^2 shape is assumed here: y=0 is not of that form. Verify
        # the ODE residual directly on the whole forward domain instead.
        h = sp.Dummy("forward_time", nonnegative=True)
        forward = candidate.subs(t, h)
        residual = sp.simplify((sp.diff(forward, h)-2*sp.sqrt(forward)).doit())
        if residual != 0:
            if residual.is_zero is None:
                raise UnsupportedMath("Full forward-domain residual remains unresolved")
            return False, candidate, f"Candidate has nonzero ODE residual {residual}."
    else:
        # Only a unit leading-coefficient square (t+C)^2 is in this finite proof.
        polynomial = sp.Poly(candidate, t)
        if polynomial.degree() != 2 or polynomial.LC() != 1:
            raise UnsupportedMath("Square-root candidates must have the reviewed (t+C)^2 form")
        shift = polynomial.nth(1)/2
        if shift.free_symbols or shift.is_real is not True or sp.expand(candidate-(t+shift)**2) != 0:
            raise UnsupportedMath("Candidate is not an established closed real shifted square")
        if shift.is_negative is True:
            point = -shift/2
            residual = sp.simplify((sp.diff(candidate, t)-2*sp.sqrt(candidate)).subs(t, point).doit())
            if residual.is_zero is not False:
                raise UnsupportedMath("Negative-shift residual witness was not established")
            return False, candidate, f"At t={point}, candidate ODE residual is {residual}; the initial condition alone is insufficient."
        if shift.is_nonnegative is not True:
            raise UnsupportedMath("Forward principal-root sign remains unresolved")
        h = sp.Dummy("forward_time", nonnegative=True)
        forward = candidate.subs(t, h)
        if sp.simplify((sp.diff(forward, h)-2*sp.sqrt(forward)).doit()) != 0:
            raise UnsupportedMath("Full forward-domain residual was not established zero")
    return True, candidate, "Initial value, C1 regularity, state and ODE identity hold on the complete declared time domain."


def verified_reference(context: Context, facts: IVPFacts) -> bool:
    # The reference must be an actually verified declared candidate; JSON does
    # not establish existence merely by calling a formula a reference solution.
    for expression in facts.spec.candidate_solutions:
        valid, candidate, _ = candidate_valid(context, facts, expression)
        if valid and sp.simplify((candidate-facts.reference).doit()) == 0:
            return True
    return False


def verified_nonuniqueness(context: Context, facts: IVPFacts) -> tuple[bool, list[sp.Expr]]:
    """Disprove uniqueness: at least two declared candidates, both actually
    verified and pairwise distinct as functions of t, never as a complete
    solution family. Declining a sufficient (Lipschitz) condition is not by
    itself used as evidence; only concrete verified witnesses are."""
    verified = []
    for expression in facts.spec.candidate_solutions:
        valid, candidate, _ = candidate_valid(context, facts, expression)
        if valid:
            verified.append(candidate)
    if len(verified) < 2:
        return False, verified
    first, second = verified[0], verified[1]
    difference = sp.simplify((first-second).doit())
    distinct = (sp.Poly(difference, facts.t).is_zero is False) if difference.is_polynomial(facts.t) else (difference.is_zero is False)
    return bool(distinct), verified
