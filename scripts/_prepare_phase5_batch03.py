"""Write private mathematical review packets only; no runtime publication."""
import copy
import json
from pathlib import Path

import sympy as sp

from app.core.parsing import parse_math

OUT = Path("docs/phase5/batch-03")
NAMES = ["x", "u", "a", "b", "c", "t", "y", "alpha", "beta"]


def expr(source=None, latex=None):
    return dict(source=source, latex=latex or sp.latex(parse_math(source, symbols=NAMES).doit()))


def predicate(left, relation, right):
    return dict(left=expr(left), relation=relation, right=expr(right))


def report(steps, method, outcome, changed, first=None, remediation=None, basis="numeric_value", formed="WellFormed"):
    return dict(step={id: dict(labels=[label]) for id, label in steps},
                method=dict(labels=[method], remediation=remediation),
                conclusion=dict(labels=["Valid"] + (["Changed Conclusion"] if changed else [])),
                comparison=dict(basis=basis, changed=changed),
                first_invalid_step_id=first, first_unresolved_step_id=None,
                problem_well_formedness=formed)


def number(source):
    return dict(status="numeric_value", value=expr(source))


def symbolic(source, scope):
    return dict(status="symbolic_formula", formula=expr(source), variable="t", solution_scope=scope)


def change(id, condition, source, description, type="parameter_value", rule_id=None):
    data = dict(id=id, condition_id=condition, type=type, new_value=expr(source), description=description)
    if rule_id:
        data["rule_id"] = rule_id
    return data


def step(id, number, before, after, assumptions=(), constraints=(), transformation="Equivalent"):
    return dict(id=id, number=number, input=expr(latex=before), output=expr(latex=after),
                method_id="original-method", assumption_ids=list(assumptions),
                transformation_kind=transformation, domain_constraints=list(constraints),
                explanation="Baseline derivation claim, subject to the explicit hypotheses and independent checking after a change.")


def problem(statement, latex, variables, name, value, condition, constraints=(), computation=None):
    return dict(statement=statement, expression=expr(latex=latex), goal=statement, variables=variables,
                parameters=[dict(name=name, value=expr(value), domain="real")],
                conditions=[dict(id=condition, parameter_name=name, description="The given real parameter "+name,
                                 predicate=predicate(name, "eq", value))],
                domain_constraints=list(constraints), computation=computation, well_formedness=None)


def assumption(id, kind, description, condition, required=None):
    return dict(id=id, kind=kind, description=description, condition_ids=[condition],
                predicate=required, state="unchecked")


def packet(no, id, topic, title, original, assumptions, steps, computation, changes, checks, cases, **extra):
    return dict(draft_version=1, matrix_number=no, id=id, topic=topic, title=title,
                review=dict(status="draft", reviewer=None,
                            basis="Private detailed mathematics awaiting Claude Code review. No batch-03 checker, IVP model or publication is implemented."),
                original_problem=original, proposed_computation=computation, assumptions=assumptions,
                methods=[dict(id="original-method", name=title, description="The specific original derivation under review.",
                              assumption_ids=[item["id"] for item in assumptions])],
                correct_steps=steps, allowed_changes=changes, planned_checks=checks, scenarios=cases, **extra)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    legacy = json.loads(Path("app/templates/data/integral-endpoint.json").read_text(encoding="utf-8"))
    ids = [item["id"] for item in legacy["correct_steps"]]
    cases = []
    for id, value, changed_id, answer in [
        ("baseline", "1/2", None, number("log(2)")),
        ("singular-endpoint", "1", "endpoint-at-pole", dict(status="divergent", value=expr(latex=r"+\infty"), signed_direction="positive")),
        ("regular-control", "3/4", "regular-endpoint", number("log(4)")),
    ]:
        singular = value == "1"
        cases.append(dict(id=id, change_id=changed_id, parameter_values={"b": value}, reference_outcome=answer,
                          derivation_claim=dict(status="undefined", value=expr(latex=r"-\log 0\ \text{is not a finite real endpoint value}")) if singular else answer,
                          expected_report=report([(item, "Invalid Step" if singular else "Valid") for item in ids],
                                                 "Needs Checking" if singular else "Valid", answer, changed_id is not None,
                                                 first=ids[0] if singular else None,
                                                 remediation="Use regular truncated substitution intervals and separately evaluate the one-sided improper-integral limit." if singular else None,
                                                 formed="Divergent" if singular else "WellFormed"),
                          mathematical_basis=["The primitive is -log(1-x) on x<1. At b=1 the separate upper one-sided limit is +infinity; direct real logarithm evaluation at zero is undefined."]))
    data = packet(11, legacy["id"], "Integration", legacy["title"], legacy["original_problem"],
                  legacy["assumptions"], legacy["correct_steps"], legacy["original_problem"]["computation"],
                  [change("endpoint-at-pole", "upper-endpoint", "1", "Move only b to 1.", "interval_endpoint", "move-upper-endpoint"),
                   change("regular-endpoint", "upper-endpoint", "3/4", "Move only b to 3/4.", "interval_endpoint", "move-upper-endpoint")],
                  [dict(id=item["id"], operation=item["kind"], step_id=next(ref["id"] for ref in item["refs"] if ref["kind"] == "step"),
                        parameters=item["parameters"]) for item in legacy["verification_rules"] if any(ref["kind"] == "step" for ref in item["refs"])],
                  cases, existing_template_snapshot=legacy, planned_outcome_checks=[legacy["verification_rules"][-1]],
                  review_note="Formal re-review only. Preserve all existing template/condition/step/rule IDs and the Phase 4 challenge bindings.")
    # Existing method ID is intentionally retained too.
    data["methods"] = legacy["methods"]
    write(data)

    c = "pole-location"
    spec = dict(kind="integral", variable="x", integrand=expr("1/(x-c)"), lower=expr("-1"), upper=expr("1"))
    steps = [
        step("primitive-on-components", 1, r"f_c(x)=\frac1{x-c}", r"F_c(x)=\log|x-c|,\quad F'_c=f_c\ (x\ne c)",
             constraints=[predicate("x", "ne", "c")]),
        step("apply-endpoint-formula", 2, r"\int_{-1}^1 f_c(x)\,dx", r"F_c(1)-F_c(-1)", ["closed-interval-regularity"]),
        step("evaluate-endpoint-expression", 3, r"\log|1-c|-\log|-1-c|", r"-\log3"),
    ]
    assumptions = [assumption("closed-interval-regularity", "continuity_on_interval",
                               "The original proper-integral endpoint formula requires continuity across the full closed interval.", c)]
    cases = []
    for id, value, changed_id, answer in [
        ("baseline", "2", None, number("-log(3)")),
        ("interior-pole", "0", "move-pole-inside", dict(status="divergent", value=expr(latex=r"\text{Divergent: opposing one-sided infinities}"), signed_direction=None)),
        ("outside-control", "3", "move-pole-outside", number("-log(2)")),
    ]:
        inside = value == "0"
        case = dict(id=id, change_id=changed_id, parameter_values={"c": value}, reference_outcome=answer,
                    derivation_claim=number("0") if inside else answer,
                    expected_report=report([(steps[0]["id"], "Valid"), (steps[1]["id"], "Invalid Step" if inside else "Valid"),
                                            (steps[2]["id"], "Valid")], "Invalid Step" if inside else "Valid", answer,
                                           changed_id is not None, first=steps[1]["id"] if inside else None,
                                           remediation="Split at the interior singularity and require both independently evaluated improper pieces to converge; they do not." if inside else None,
                                           formed="Divergent" if inside else "WellFormed"),
                    mathematical_basis=["Primitive differentiation is valid separately on each component x!=c, not across the removed point. A missing proper-integral hypothesis alone is not the failure proof; the two divergent pieces independently refute a finite total."])
        if inside:
            case["one_sided_pieces"] = [dict(interval=[expr("-1"), expr("0")], value=expr(latex=r"-\infty"), signed_direction="negative"),
                                       dict(interval=[expr("0"), expr("1")], value=expr(latex=r"+\infty"), signed_direction="positive")]
            case["symmetric_principal_value"] = dict(value=expr("0"), is_requested_answer=False)
        cases.append(case)
    checks = [dict(operation="primitive_identity_on_components", step_id=steps[0]["id"], variable="x", primitive=expr("log(abs(x-c))")),
              dict(operation="proper_integral_endpoint_formula", step_id=steps[1]["id"], primitive=expr("log(abs(x-c))")),
              dict(operation="evaluate_scalar", step_id=steps[2]["id"], expression=expr("log(abs(1-c))-log(abs(-1-c))"), value_domain="real")]
    write(packet(12, "integral-interior-pole", "Integration", "Opposing interior infinities do not cancel into an integral",
                 problem("Evaluate the ordinary real integral on [-1,1], initially c=2; no principal value is requested.",
                         r"\int_{-1}^{1}\frac{dx}{x-c}", {"x": "real"}, "c", "2", c, [predicate("x", "ne", "c")], spec),
                 assumptions, steps, spec,
                 [change("move-pole-inside", c, "0", "Move c=2 to c=0."), change("move-pole-outside", c, "3", "Move c=2 to c=3.")],
                 checks, cases, planned_outcome_checks=[dict(operation="split_improper_integral", discover_from="actual rational integrand and actual bounds", combine_only_if_each_piece_converges=True)]))

    c = "pole-separation"
    spec = dict(kind="integral", variable="x", integrand=expr("1/(x*(x-a))"), lower=expr("2"), upper=expr("3"))
    primitive = "(log(abs(x-a))-log(abs(x)))/a"
    endpoint = "(log(abs(3-a))-log(3)-log(abs(2-a))+log(2))/a"
    steps = [
        step("choose-distinct-pole-form", 1, r"\frac1{x(x-a)}", r"\frac{\alpha}{x}+\frac{\beta}{x-a}", ["distinct-poles"]),
        step("solve-distinct-coefficients", 2, r"1=\alpha(x-a)+\beta x", r"\alpha=-\frac1a,\quad\beta=\frac1a", ["distinct-poles"]),
        step("integrate-distinct-terms", 3, r"-\frac1{ax}+\frac1{a(x-a)}", r"F_a(x)=\frac{\log|x-a|-\log|x|}{a}", ["distinct-poles"]),
        step("evaluate-distinct-form", 4, r"F_a(3)-F_a(2)", r"\log\frac43", ["distinct-poles", "closed-interval-regularity"]),
    ]
    assumptions = [assumption("distinct-poles", "nonzero", "The distinct-simple-pole ansatz and its 1/a coefficients require a!=0.", c, predicate("a", "ne", "0")),
                   assumption("closed-interval-regularity", "continuity_on_interval", "The actual integrand must be continuous on [2,3] for proper endpoint evaluation.", c)]
    cases = []
    for id, value, changed_id, answer in [
        ("baseline", "1", None, number("log(4/3)")),
        ("coincident-poles", "0", "merge-poles", number("1/6")),
        ("distinct-control", "-1", "negative-separation", number("log(9/8)")),
    ]:
        merged = value == "0"
        case = dict(id=id, change_id=changed_id, parameter_values={"a": value}, reference_outcome=answer,
                    derivation_claim=dict(status="undefined", value=expr(latex=r"\text{The distinct-pole formula divides by zero}")) if merged else answer,
                    expected_report=report([(item["id"], "Invalid Step" if merged else "Valid") for item in steps],
                                           "Needs Checking" if merged else "Valid", answer, changed_id is not None,
                                           first=steps[0]["id"] if merged else None,
                                           remediation="Replace the collapsed distinct-pole ansatz by alpha/x+beta/x^2; verify alpha=0,beta=1 and integrate -1/x." if merged else None),
                    mathematical_basis=["Matching constant coefficients gives alpha+beta=0 and -a*alpha=1. At a=0 these are inconsistent; the actual integrand is 1/x^2, continuous on [2,3]. No integral divergence is present."])
        if merged:
            case["verified_repair"] = dict(ansatz=expr("alpha/x+beta/x**2"), coefficients={"alpha": "0", "beta": "1"},
                                           primitive=expr("-1/x"), value=expr("1/6"))
        cases.append(case)
    write(packet(13, "integral-coalescing-poles", "Integration", "A repeated pole needs a different partial-fraction form",
                 problem("Evaluate the proper real integral on [2,3], initially a=1. The poles lie outside this interval in every declared case.",
                         r"\int_2^3\frac{dx}{x(x-a)}", {"x": "real", "alpha": "real", "beta": "real"}, "a", "1", c,
                         [predicate("x", "ne", "0"), predicate("x", "ne", "a")], spec),
                 assumptions, steps, spec,
                 [change("merge-poles", c, "0", "Merge the simple poles at zero."), change("negative-separation", c, "-1", "Keep two distinct poles outside [2,3].")],
                 [dict(operation="two_pole_ansatz", step_id=steps[0]["id"], variable="x", coefficient_names=["alpha", "beta"], ansatz=expr("alpha/x+beta/(x-a)")),
                  dict(operation="two_pole_coefficients", step_id=steps[1]["id"], coefficient_values={"alpha": expr("-1/a"), "beta": expr("1/a")}),
                  dict(operation="two_pole_primitive", step_id=steps[2]["id"], primitive=expr(primitive)),
                  dict(operation="two_pole_endpoint_value", step_id=steps[3]["id"], expression=expr(endpoint))],
                 cases, coefficient_scope="alpha and beta are constants independent of x, not arbitrary functions.",
                 planned_outcome_checks=[dict(operation="definite_integral", verify_repeated_pole_repair_from_actual_denominator=True)]))

    c = "initial-amplitude"
    time_r = dict(lower=None, upper=None, left_closed=False, right_closed=False)
    spec = dict(kind="first_order_ivp", independent_variable="t", dependent_variable="y", rhs=expr("y"),
                initial_time=expr("0"), initial_value=expr("a"), time_domain=time_r, state_domain=dict(number_system="real", constraints=[]),
                question="solution", solution_scope="unique_solution", candidate_solutions=[expr("a*exp(t)")])
    steps = [
        step("divide-by-state", 1, r"y'=y", r"\frac{y'}y=1", ["nonzero-initial-state"], [predicate("y", "ne", "0")]),
        step("integrate-log-state", 2, r"\frac{y'}y=1", r"\log|y|=t+C", ["nonzero-initial-state"], [predicate("y", "ne", "0")]),
        step("apply-log-initial-value", 3, r"y(0)=a", r"C=\log|a|,\quad \operatorname{sgn}y=\operatorname{sgn}a", ["nonzero-initial-state"]),
        step("verify-original-ivp", 4, r"y_a(t)=ae^t", r"y'_a=y_a,\quad y_a(0)=a", transformation="OneWayImplication"),
    ]
    assumptions = [assumption("nonzero-initial-state", "nonzero", "For this verified linear family, a!=0 implies the trajectory never vanishes; division and log|y| are then defined.", c, predicate("a", "ne", "0"))]
    cases = []
    for id, value, changed_id in [("baseline", "1", None), ("zero-equilibrium", "0", "zero-initial-state"),
                                   ("positive-control", "2", "positive-initial-state"), ("negative-control", "-1", "negative-initial-state")]:
        zero = value == "0"
        formula = "0" if zero else value+"*exp(t)"
        answer = symbolic(formula, "unique_solution")
        cases.append(dict(id=id, change_id=changed_id, parameter_values={"a": value}, reference_outcome=answer,
                          derivation_claim=answer,
                          expected_report=report([(item["id"], "Invalid Step" if zero and i < 3 else "Valid") for i, item in enumerate(steps)],
                                                 "Needs Checking" if zero else "Valid", answer, changed_id is not None,
                                                 first=steps[0]["id"] if zero else None,
                                                 remediation="Retain the zero equilibrium as a separate case and verify it in the original IVP; apply logarithmic separation only on nonzero trajectories." if zero else None,
                                                 basis="symbolic_formula"),
                          mathematical_basis=["The candidate a*exp(t) satisfies the original equation and initial data for every real a. For every C1 solution, (exp(-t)*y(t))'=0, forcing y=a*exp(t); this proves global uniqueness without dsolve.",
                                              "At a=0 the unique trajectory is identically zero, so division by y and log|y| are undefined; the final candidate check is independently valid. Negative a retains its initial sign and does not become +exp(t)."]))
    write(packet(14, "ivp-zero-equilibrium", "Differential Equations", "Separation can discard a zero equilibrium",
                 problem("Solve y'=y, y(0)=a on all real time, initially a=1.", r"y'=y,\quad y(0)=a,\quad t\in\mathbb R",
                         {"t": "real", "y": "real"}, "a", "1", c),
                 assumptions, steps, spec,
                 [change("zero-initial-state", c, "0", "Set the initial state to zero."), change("positive-initial-state", c, "2", "Set the initial state to two."),
                  change("negative-initial-state", c, "-1", "Set the initial state to minus one.")],
                 [dict(operation="linear_ivp_division", step_id=steps[0]["id"], divisor=expr("y")),
                  dict(operation="linear_ivp_log_separation", step_id=steps[1]["id"], state_expression=expr("log(abs(y))")),
                  dict(operation="linear_ivp_initial_constant", step_id=steps[2]["id"], expression=expr("log(abs(a))"), retain_initial_sign=True),
                  dict(operation="ivp_candidate_substitution", step_id=steps[3]["id"], candidate=expr("a*exp(t)"))],
                 cases, family_verification="Normalize the actual rhs and verify it equals the dependent variable; a declared family label alone is not evidence.",
                 independent_uniqueness_proof="For every solution, (exp(-t)*y)'=exp(-t)*(y'-y)=0. Initial data fixes the constant a.",
                 comparison_scope="Compare the computed solution functions on the stated full real time domain, not display strings or their common value at t=0 alone."))

    time_forward = dict(lower=expr("0"), upper=None, left_closed=True, right_closed=False)
    spec = dict(kind="first_order_ivp", independent_variable="t", dependent_variable="y", rhs=expr("2*sqrt(y)"),
                initial_time=expr("0"), initial_value=expr("a*a"), time_domain=time_forward,
                state_domain=dict(number_system="real", constraints=[predicate("y", "ge", "0")]),
                question="solution", solution_scope="verified_witness", candidate_solutions=[expr("(t+abs(a))**2")])
    assumptions = [
        assumption("positive-initial-state", "parameter_range", "All listed initial states a^2 are positive. In this actual nonnegative-rhs family, a forward solution therefore stays positive.", c, predicate("a*a", "gt", "0")),
        assumption("principal-initial-sign", "parameter_range", "Replacing sqrt(a^2) by a in the initial constant requires a>=0.", c, predicate("a", "ge", "0")),
    ]
    steps = [
        step("positive-root-substitution", 1, r"y'=2\sqrt y,\quad u=\sqrt y>0", r"2uu'=2u", ["positive-initial-state"], [predicate("u", "gt", "0")]),
        step("integrate-root-state", 2, r"2uu'=2u,\quad u>0", r"u'=1,\quad u=t+C", ["positive-initial-state"], [predicate("u", "gt", "0")]),
        step("choose-initial-root", 3, r"C=u(0)=\sqrt{a^2}", r"C=a", ["principal-initial-sign"]),
        step("verify-forward-candidate", 4, r"y_a(t)=(t+a)^2,\quad t\ge0", r"y'_a=2\sqrt{y_a},\quad y_a(0)=a^2", transformation="OneWayImplication"),
    ]
    cases = []
    for id, value, changed_id, source in [("baseline", "1", None, "(t+1)**2"),
                                         ("negative-amplitude", "-1", "flip-amplitude-sign", "(t+1)**2"),
                                         ("positive-control", "2", "increase-amplitude", "(t+2)**2")]:
        bad = value == "-1"
        answer = symbolic(source, "verified_witness")
        case = dict(id=id, change_id=changed_id, parameter_values={"a": value}, reference_outcome=answer,
                    derivation_claim=symbolic("(t-1)**2" if bad else source, "verified_witness"),
                    expected_report=report([(item["id"], "Invalid Step" if bad and i >= 2 else "Valid") for i, item in enumerate(steps)],
                                           "Needs Checking" if bad else "Valid", answer, value == "2",
                                           first=steps[2]["id"] if bad else None,
                                           remediation="Use the actual principal initial root C=abs(a), then verify (t+abs(a))^2 on the entire forward time domain." if bad else None,
                                           basis="symbolic_formula"),
                    mathematical_basis=["The actual principal root at time zero is abs(a). The repaired forward candidate (t+abs(a))^2 has residual zero for every t>=0 and satisfies y(0)=a^2.",
                                        "For a=-1 the unrepaired candidate (t-1)^2 satisfies the initial condition and is nonnegative, but has residual 4*(t-1) on 0<=t<1; it fails the ODE on the required interval. No uniqueness or complete-solution-family claim is made."])
        if bad:
            case["counterexample"] = dict(time=expr("1/2"), candidate_value=expr("1/4"), derivative=expr("-1"), rhs=expr("1"), residual=expr("-2"))
            case["same_ivp_as_baseline"] = True
        cases.append(case)
    write(packet(15, "ivp-principal-initial-root", "Differential Equations", "An initial square root cannot forget its sign",
                 problem("Find one C1 forward solution of y'=2sqrt(y), y(0)=a^2 for t>=0, initially a=1. Do not claim a complete solution family.",
                         r"y'=2\sqrt y,\quad y(0)=a^2,\quad t\ge0,\quad y\ge0", {"t": "real", "y": "real", "u": "real"}, "a", "1", c),
                 assumptions, steps, spec,
                 [change("flip-amplitude-sign", c, "-1", "Flip only the given amplitude a from 1 to -1."),
                  change("increase-amplitude", c, "2", "Increase the positive amplitude from 1 to 2.")],
                 [dict(operation="sqrt_ivp_substitution", step_id=steps[0]["id"], root_variable="u"),
                  dict(operation="sqrt_ivp_root_integration", step_id=steps[1]["id"], root_variable="u"),
                  dict(operation="ivp_principal_initial_root", step_id=steps[2]["id"], claimed_constant=expr("a")),
                  dict(operation="ivp_candidate_substitution", step_id=steps[3]["id"], candidate=expr("(t+a)**2"))],
                 cases, family_verification="Verify the actual rhs is 2*sqrt(y), state domain is y>=0 and time domain is forward from the declared initial time; labels alone cannot enable the checker.",
                 comparison_scope="The reference output is one verified forward witness, not the full solution set or a uniqueness property. At a=1 and a=-1 the actual IVP and repaired witness coincide.",
                 next_batch_boundary="The previously planned No.16 changes a nonnegative initial value to zero and asks about uniqueness with two concrete witnesses. That is deliberately not part of this No.15 draft."))


def write(data):
    if data["matrix_number"] in (12, 13, 14, 15):
        name, description = {
            12: ("Single-interval endpoint evaluation", "Claim that one global F(upper)-F(lower) evaluates the ordinary integral without splitting. A componentwise primitive identity alone does not justify this claim."),
            13: ("Partial fractions", "The displayed derivation uses distinct simple poles. A verified repeated-pole ansatz can repair the same partial-fraction technique."),
            14: ("Separation of variables", "The displayed logarithmic separation divides by y; a zero equilibrium requires a separately verified case."),
            15: ("Positive-root substitution", "Use u=sqrt(y) on positive forward trajectories; the displayed initial-constant choice assumes the given amplitude is nonnegative."),
        }[data["matrix_number"]]
        data["methods"][0].update(name=name, description=description)
    target = OUT / f"{data['matrix_number']:02d}-{data['id']}.json"
    target.write_text(json.dumps(copy.deepcopy(data), ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


if __name__ == "__main__":
    main()
