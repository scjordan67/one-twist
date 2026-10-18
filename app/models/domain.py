from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Identifier = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]*$")]
NonEmpty = Annotated[str, Field(min_length=1)]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ValidityLabel(StrEnum):
    VALID = "Valid"
    NEEDS_CHECKING = "Needs Checking"
    INCONVENIENT = "Inconvenient"
    INVALID_STEP = "Invalid Step"
    CHANGED_CONCLUSION = "Changed Conclusion"
    UNKNOWN = "Unknown"


class WellFormedness(StrEnum):
    WELL_FORMED = "WellFormed"
    NO_SOLUTION = "NoSolution"
    DIVERGENT = "Divergent"
    UNDEFINED = "Undefined"
    CONTRADICTORY_CONDITIONS = "ContradictoryConditions"


class TransformationKind(StrEnum):
    EQUIVALENT = "Equivalent"
    ONE_WAY_IMPLICATION = "OneWayImplication"
    CASE_SPLIT = "CaseSplit"


class AssumptionState(StrEnum):
    ASSUMED_TRUE = "assumed_true"
    PERTURBED_REMOVED = "perturbed_removed"
    PERTURBED_FALSE = "perturbed_false"
    UNCHECKED = "unchecked"


class EvidenceRef(Model):
    kind: Literal["step", "assumption", "condition"]
    id: Identifier


class Evidence(Model):
    rule_id: Identifier
    summary: NonEmpty
    origin: Literal["computed", "author_reviewed"] = "computed"
    outcome: str | None = None


class DimensionResult(Model):
    labels: Annotated[set[ValidityLabel], Field(min_length=1)]
    evidence: list[Evidence] = Field(default_factory=list)
    affected_refs: list[EvidenceRef] = Field(default_factory=list)
    reason_if_unknown: NonEmpty | None = None
    remediation: NonEmpty | None = None

    @model_validator(mode="after")
    def check_label_requirements(self) -> Self:
        if ValidityLabel.UNKNOWN in self.labels and self.reason_if_unknown is None:
            raise ValueError("Unknown requires reason_if_unknown")
        if ValidityLabel.INCONVENIENT in self.labels and not any(
            item.origin == "author_reviewed" for item in self.evidence
        ):
            raise ValueError("Inconvenient requires author-reviewed evidence")
        return self


class MathExpression(Model):
    # None means display-only mathematics outside the Phase 1 input grammar.
    source: NonEmpty | None = None
    latex: NonEmpty


class Predicate(Model):
    left: MathExpression
    relation: Literal["eq", "ne", "lt", "le", "gt", "ge"]
    right: MathExpression


class Parameter(Model):
    name: Identifier
    value: MathExpression
    domain: Literal["real", "complex", "integer"] = "real"


class DomainSpec(Model):
    number_system: Literal["real", "complex", "integer"] = "real"
    constraints: list[Predicate] = Field(default_factory=list)

    @model_validator(mode="after")
    def no_complex_ordering(self) -> Self:
        if self.number_system == "complex" and any(item.relation not in {"eq", "ne"} for item in self.constraints):
            raise ValueError("Complex domains cannot contain ordering predicates")
        return self


class DomainConditionBinding(Model):
    kind: Literal["domain"] = "domain"
    variable: Identifier
    current: DomainSpec


class DomainChoice(Model):
    id: Identifier
    label: NonEmpty
    domain: DomainSpec


class Condition(Model):
    id: Identifier
    description: NonEmpty
    predicate: Predicate | None = None
    parameter_name: Identifier | None = None
    domain_binding: DomainConditionBinding | None = None

    @model_validator(mode="after")
    def one_binding(self) -> Self:
        if self.domain_binding is not None and (self.parameter_name is not None or self.predicate is not None):
            raise ValueError("A domain condition owns its constraints only through domain_binding")
        return self


class EquationSpec(Model):
    kind: Literal["equation"] = "equation"
    variable: Identifier
    left: MathExpression
    right: MathExpression


class IntervalSpec(Model):
    variable: Identifier
    lower: MathExpression
    upper: MathExpression


class IntegralSpec(IntervalSpec):
    kind: Literal["integral"] = "integral"
    integrand: MathExpression


class ScalarExpressionSpec(Model):
    kind: Literal["scalar_expression"] = "scalar_expression"
    expression: MathExpression
    value_domain: Literal["real", "complex"] = "real"


class DerivativeAtPointSpec(Model):
    kind: Literal["derivative_at_point"] = "derivative_at_point"
    variable: Identifier
    expression: MathExpression
    point: MathExpression


class StationaryPointSpec(Model):
    kind: Literal["stationary_point"] = "stationary_point"
    variable: Identifier
    expression: MathExpression
    point: MathExpression


class LimitSpec(Model):
    kind: Literal["limit"] = "limit"
    variable: Identifier
    expression: MathExpression
    point: MathExpression
    direction: Literal["both", "left", "right"] = "both"


class TimeDomain(Model):
    lower: MathExpression | None = None
    upper: MathExpression | None = None
    left_closed: bool = False
    right_closed: bool = False

    @model_validator(mode="after")
    def infinity_is_open(self) -> Self:
        if (self.lower is None and self.left_closed) or (self.upper is None and self.right_closed):
            raise ValueError("An unbounded time endpoint cannot be closed")
        return self


class FirstOrderIVPSpec(Model):
    kind: Literal["first_order_ivp"] = "first_order_ivp"
    independent_variable: Identifier
    dependent_variable: Identifier
    rhs: MathExpression
    initial_time: MathExpression
    initial_value: MathExpression
    time_domain: TimeDomain
    state_domain: DomainSpec
    question: Literal["solution"] = "solution"
    solution_scope: Literal["unique_solution", "verified_witness", "nonuniqueness_witnesses"]
    candidate_solutions: Annotated[list[MathExpression], Field(min_length=1, max_length=2)]

    @model_validator(mode="after")
    def nonuniqueness_needs_two_witnesses(self) -> Self:
        if self.solution_scope == "nonuniqueness_witnesses" and len(self.candidate_solutions) != 2:
            raise ValueError("Disproving uniqueness requires exactly two declared candidate witnesses")
        return self

    @model_validator(mode="after")
    def distinct_variables(self) -> Self:
        if self.independent_variable == self.dependent_variable:
            raise ValueError("IVP time and state variables must differ")
        return self


ComputationSpec = Annotated[
    EquationSpec | IntegralSpec | ScalarExpressionSpec | DerivativeAtPointSpec | StationaryPointSpec | LimitSpec | FirstOrderIVPSpec,
    Field(discriminator="kind"),
]


class EquationTransform(Model):
    operation: Literal["equation_transform"] = "equation_transform"
    before: EquationSpec
    after: EquationSpec
    divisor: MathExpression | None = None


class SubstitutionCheck(Model):
    operation: Literal["substitution"] = "substitution"
    mapping: MathExpression
    transformed: IntegralSpec


class AntiderivativeCheck(Model):
    operation: Literal["antiderivative"] = "antiderivative"
    primitive: MathExpression


class EvaluationCheck(Model):
    operation: Literal["evaluate_expression"] = "evaluate_expression"
    expression: MathExpression
    result_variable: Identifier | None = None


class ExpressionIdentityCheck(Model):
    operation: Literal["expression_identity"] = "expression_identity"
    left: MathExpression
    right: MathExpression
    value_domain: Literal["real", "complex"] = "real"


class ScalarEvaluationCheck(Model):
    operation: Literal["evaluate_scalar"] = "evaluate_scalar"
    expression: MathExpression
    value_domain: Literal["real", "complex"] = "real"


class SolveCandidatesCheck(Model):
    operation: Literal["solve_candidates"] = "solve_candidates"
    equation: EquationSpec


class CandidateAcceptanceCheck(Model):
    operation: Literal["candidate_acceptance"] = "candidate_acceptance"
    candidates_from: EquationSpec
    original: EquationSpec


class DomainPredicateCheck(Model):
    operation: Literal["domain_predicate"] = "domain_predicate"
    variable: Identifier
    required: Predicate


class CandidatePredicateCheck(Model):
    operation: Literal["candidate_predicate"] = "candidate_predicate"
    variable: Identifier
    candidates_from: EquationSpec
    required: Predicate

    @model_validator(mode="after")
    def candidate_variable(self) -> Self:
        if self.variable != self.candidates_from.variable:
            raise ValueError("Candidate predicate and equation variables must agree")
        return self


class PrincipalSineCheck(Model):
    operation: Literal["principal_sine_inverse", "principal_sine_completeness"]
    equation: EquationSpec


class PrincipalSineCoverageCheck(Model):
    operation: Literal["principal_sine_coverage"] = "principal_sine_coverage"
    equation: EquationSpec


class EvaluatePrincipalSineCheck(Model):
    operation: Literal["evaluate_principal_sine"] = "evaluate_principal_sine"
    argument: MathExpression


class DerivativeIdentityCheck(Model):
    operation: Literal["derivative_identity_on_domain"] = "derivative_identity_on_domain"
    expression: MathExpression
    variable: Identifier
    claimed_derivative: MathExpression


class DerivativePointSubstitutionCheck(Model):
    operation: Literal["derivative_point_substitution"] = "derivative_point_substitution"
    variable: Identifier
    point: MathExpression
    formula: MathExpression


class PointFormulaCheck(DerivativePointSubstitutionCheck):
    operation: Literal["point_formula_defined"] = "point_formula_defined"


class StationaryValueCheck(Model):
    operation: Literal["stationary_point_check", "second_derivative_value"]
    expression: MathExpression
    variable: Identifier
    point: MathExpression


StationaryClassification = Literal["local_minimum", "local_maximum", "stationary_non_extremum"]


class ClaimStationaryClassificationCheck(Model):
    operation: Literal["claim_stationary_classification"] = "claim_stationary_classification"
    classification: StationaryClassification
    method: Literal["strict_second_derivative"] = "strict_second_derivative"


class DifferentiateLimitComponentsCheck(Model):
    operation: Literal["differentiate_limit_components"] = "differentiate_limit_components"
    variable: Identifier
    numerator: MathExpression
    denominator: MathExpression


class LHopitalReplacementCheck(DifferentiateLimitComponentsCheck):
    operation: Literal["lhopital_replacement"] = "lhopital_replacement"
    point: MathExpression
    direction: Literal["both"] = "both"
    required_form: Literal["zero_over_zero"] = "zero_over_zero"


class LHopitalPremiseCheck(LHopitalReplacementCheck):
    operation: Literal["lhopital_zero_over_zero"] = "lhopital_zero_over_zero"


class EvaluateLimitCheck(Model):
    operation: Literal["evaluate_limit"] = "evaluate_limit"
    variable: Identifier
    point: MathExpression
    expression: MathExpression


class PrimitiveComponentsCheck(Model):
    operation: Literal["primitive_identity_on_components"] = "primitive_identity_on_components"
    variable: Identifier
    primitive: MathExpression


class ProperEndpointCheck(Model):
    operation: Literal["proper_integral_endpoint_formula"] = "proper_integral_endpoint_formula"
    primitive: MathExpression


class TwoPoleAnsatzCheck(Model):
    operation: Literal["two_pole_ansatz"] = "two_pole_ansatz"
    variable: Identifier
    coefficient_names: tuple[Identifier, Identifier]
    ansatz: MathExpression


class TwoPoleCoefficientsCheck(Model):
    operation: Literal["two_pole_coefficients"] = "two_pole_coefficients"
    coefficient_values: dict[Literal["alpha", "beta"], MathExpression]

    @model_validator(mode="after")
    def both_coefficients(self) -> Self:
        if set(self.coefficient_values) != {"alpha", "beta"}:
            raise ValueError("Both reviewed coefficient values are required")
        return self


class TwoPolePrimitiveCheck(Model):
    operation: Literal["two_pole_primitive"] = "two_pole_primitive"
    primitive: MathExpression


class TwoPoleEndpointCheck(Model):
    operation: Literal["two_pole_endpoint_value"] = "two_pole_endpoint_value"
    expression: MathExpression


class LinearDivisionCheck(Model):
    operation: Literal["linear_ivp_division"] = "linear_ivp_division"
    divisor: MathExpression


class LinearLogCheck(Model):
    operation: Literal["linear_ivp_log_separation"] = "linear_ivp_log_separation"
    state_expression: MathExpression


class LinearInitialCheck(Model):
    operation: Literal["linear_ivp_initial_constant"] = "linear_ivp_initial_constant"
    expression: MathExpression
    retain_initial_sign: Literal[True] = True


class IVPCandidateCheck(Model):
    operation: Literal["ivp_candidate_substitution"] = "ivp_candidate_substitution"
    candidate: MathExpression


class RootRateCheck(Model):
    operation: Literal["sqrt_ivp_rate_division"] = "sqrt_ivp_rate_division"
    root_variable: Identifier


class SqrtSubstitutionCheck(Model):
    operation: Literal["sqrt_ivp_substitution"] = "sqrt_ivp_substitution"
    root_variable: Identifier


class SqrtIntegrationCheck(Model):
    operation: Literal["sqrt_ivp_root_integration"] = "sqrt_ivp_root_integration"
    root_variable: Identifier


class InitialRootCheck(Model):
    operation: Literal["ivp_principal_initial_root"] = "ivp_principal_initial_root"
    claimed_constant: MathExpression


AssumptionCheck = Annotated[
    DomainPredicateCheck | CandidatePredicateCheck | PrincipalSineCoverageCheck | PointFormulaCheck | LHopitalPremiseCheck,
    Field(discriminator="operation"),
]


RuleParameters = Annotated[
    EquationTransform | SubstitutionCheck | AntiderivativeCheck | EvaluationCheck
    | ExpressionIdentityCheck | ScalarEvaluationCheck | SolveCandidatesCheck | CandidateAcceptanceCheck
    | PrincipalSineCheck | EvaluatePrincipalSineCheck | DerivativeIdentityCheck | DerivativePointSubstitutionCheck
    | StationaryValueCheck | ClaimStationaryClassificationCheck | DifferentiateLimitComponentsCheck
    | LHopitalReplacementCheck | EvaluateLimitCheck | RootRateCheck
    | PrimitiveComponentsCheck | ProperEndpointCheck | TwoPoleAnsatzCheck | TwoPoleCoefficientsCheck
    | TwoPolePrimitiveCheck | TwoPoleEndpointCheck | LinearDivisionCheck | LinearLogCheck
    | LinearInitialCheck | IVPCandidateCheck | SqrtSubstitutionCheck | SqrtIntegrationCheck | InitialRootCheck,
    Field(discriminator="operation"),
]


class Problem(Model):
    statement: NonEmpty
    expression: MathExpression
    goal: NonEmpty
    variables: dict[Identifier, Literal["real", "complex", "integer"]]
    parameters: list[Parameter] = Field(default_factory=list)
    conditions: list[Condition]
    domain_constraints: list[Predicate] = Field(default_factory=list)
    # Unassessed problems must not acquire a successful default judgement.
    well_formedness: WellFormedness | None = None
    computation: ComputationSpec | None = None

    @model_validator(mode="after")
    def unique_symbols(self) -> Self:
        names = [item.name for item in self.parameters]
        if len(names) != len(set(names)) or set(names) & self.variables.keys():
            raise ValueError("Variable and parameter names must be distinct")
        owned = set()
        for condition in self.conditions:
            binding = condition.domain_binding
            if binding is None:
                continue
            if binding.variable not in self.variables or binding.variable in owned:
                raise ValueError("A domain condition needs one distinct declared variable")
            owned.add(binding.variable)
            if self.variables[binding.variable] != binding.current.number_system:
                raise ValueError("Variable number system must match its domain condition")
            if any(item in self.domain_constraints for item in binding.current.constraints):
                raise ValueError("A constraint cannot have both fixed and mutable domain ownership")
        return self


class Assumption(Model):
    id: Identifier
    kind: NonEmpty
    description: NonEmpty
    condition_ids: list[Identifier] = Field(default_factory=list)
    predicate: Predicate | None = None
    state: AssumptionState = AssumptionState.UNCHECKED
    interval: IntervalSpec | None = None
    check: AssumptionCheck | None = None

    @model_validator(mode="after")
    def explicit_scope(self) -> Self:
        operation = {"domain_predicate": "domain_predicate", "candidate_sign": "candidate_predicate",
                     "principal_sine_coverage": "principal_sine_coverage", "point_formula_defined": "point_formula_defined",
                     "lhopital_zero_over_zero": "lhopital_zero_over_zero"}.get(self.kind)
        if operation is not None and (self.check is None or self.check.operation != operation):
            raise ValueError("Scoped assumption requires its matching typed check")
        if self.check is not None:
            if operation != self.check.operation or self.interval is not None:
                raise ValueError("Scoped assumption check must agree with kind and cannot also use interval")
            if isinstance(self.check, (DomainPredicateCheck, CandidatePredicateCheck)) and self.predicate is not None and self.predicate != self.check.required:
                raise ValueError("Displayed assumption predicate must match its typed check")
        return self


class Method(Model):
    id: Identifier
    name: NonEmpty
    description: NonEmpty
    assumption_ids: list[Identifier] = Field(default_factory=list)


class Step(Model):
    id: Identifier
    number: Annotated[int, Field(ge=1)]
    input: MathExpression
    output: MathExpression
    method_id: Identifier
    assumption_ids: list[Identifier] = Field(default_factory=list)
    transformation_kind: TransformationKind
    domain_constraints: list[Predicate] = Field(default_factory=list)
    verification: DimensionResult | None = None
    explanation: NonEmpty

    @model_validator(mode="after")
    def no_conflicting_verdict(self) -> Self:
        if self.verification is not None and {
            ValidityLabel.VALID, ValidityLabel.INVALID_STEP
        } <= self.verification.labels:
            raise ValueError("A single step cannot be both Valid and Invalid Step")
        return self


PerturbationType = Literal[
    "parameter_value", "parameter_sign", "parameter_zero", "interval_endpoint",
    "domain", "boundary", "degenerate_value", "remove_assumption", "replace_assumption",
]


class PerturbationRule(Model):
    id: Identifier
    condition_id: Identifier
    type: PerturbationType
    description: NonEmpty
    allowed_values: list[MathExpression] = Field(default_factory=list)
    assumption_id: Identifier | None = None
    domain_choices: list[DomainChoice] = Field(default_factory=list)


class Perturbation(Model):
    template_id: Identifier
    rule_id: Identifier
    condition_id: Identifier
    type: PerturbationType
    new_value: MathExpression | None = None
    choice_id: Identifier | None = None

    @model_validator(mode="after")
    def choice_payload(self) -> Self:
        if self.type == "domain":
            if self.choice_id is None or self.new_value is not None:
                raise ValueError("Domain change requires choice_id and no new_value")
        elif self.choice_id is not None:
            raise ValueError("choice_id is only accepted for domain changes")
        return self


class ConclusionComparison(Model):
    basis: Literal["numeric_value", "symbolic_formula", "classification"]
    original: MathExpression
    perturbed: MathExpression | None = None
    # None means not established, not unchanged.
    changed: bool | None = None


class ConclusionResult(Model):
    status: Literal["numeric_value", "solution_set", "divergent", "undefined", "unknown", "classification", "symbolic_formula"]
    value: MathExpression | None = None
    completeness: Literal["complete", "partial", "conditional"] | None = None
    reason_if_unknown: NonEmpty | None = None
    classification: StationaryClassification | None = None
    solution_scope: Literal["unique_solution", "verified_witness", "nonuniqueness_witnesses"] | None = None
    variable: Identifier | None = None
    time_domain: TimeDomain | None = None

    @model_validator(mode="after")
    def consistent_result(self) -> Self:
        if self.status == "unknown" and self.reason_if_unknown is None:
            raise ValueError("Unknown conclusion requires a reason")
        if self.status not in {"unknown", "classification"} and self.value is None:
            raise ValueError("Established conclusion requires a value")
        if (self.status == "classification") != (self.classification is not None):
            raise ValueError("Classification requires its typed payload, which is forbidden for other statuses")
        if self.status == "solution_set" and self.completeness is None:
            raise ValueError("Solution set requires completeness")
        symbolic = self.status == "symbolic_formula"
        if symbolic != (self.solution_scope is not None) or symbolic != (self.variable is not None) or symbolic != (self.time_domain is not None):
            raise ValueError("Symbolic IVP formulas require scope, variable and time domain exclusively")
        return self


class AssumptionResult(Model):
    status: Literal["satisfied", "violated", "needs_checking", "unknown"]
    evidence: Evidence
    reason: NonEmpty | None = None


class ValidityReport(Model):
    problem_well_formedness: WellFormedness | None = None
    step: dict[Identifier, DimensionResult]
    method: DimensionResult
    conclusion: DimensionResult
    comparison: ConclusionComparison | None = None
    first_invalid_step_id: Identifier | None = None
    first_unresolved_step_id: Identifier | None = None
    assumptions: dict[Identifier, AssumptionResult] = Field(default_factory=dict)
    original_outcome: ConclusionResult | None = None
    perturbed_outcome: ConclusionResult | None = None

    @model_validator(mode="after")
    def consistent_step_results(self) -> Self:
        for result in self.step.values():
            if {ValidityLabel.VALID, ValidityLabel.INVALID_STEP} <= result.labels:
                raise ValueError("A single step cannot be both Valid and Invalid Step")
        if self.first_invalid_step_id is not None:
            result = self.step.get(self.first_invalid_step_id)
            if result is None or ValidityLabel.INVALID_STEP not in result.labels:
                raise ValueError("first_invalid_step_id must reference an invalid step")
        if self.first_unresolved_step_id is not None:
            result = self.step.get(self.first_unresolved_step_id)
            if result is None or not result.labels & {
                ValidityLabel.UNKNOWN, ValidityLabel.NEEDS_CHECKING
            }:
                raise ValueError("first_unresolved_step_id must reference an unresolved step")
        return self


class VerificationRule(Model):
    id: Identifier
    kind: NonEmpty
    refs: list[EvidenceRef]
    description: NonEmpty
    parameters: RuleParameters | None = None


class EvidenceMatch(Model):
    rule_id: Identifier
    outcome: NonEmpty


class ExplanationFragment(Model):
    id: Identifier
    evidence_keys: list[Identifier]
    text: NonEmpty
    when: list[EvidenceMatch] = Field(default_factory=list)


class Review(Model):
    status: Literal["draft", "reviewed"] = "draft"
    reviewer: NonEmpty | None = None
    basis: NonEmpty


def unique_ids(items: list, name: str) -> set[str]:
    ids = [item.id for item in items]
    if len(ids) != len(set(ids)):
        raise ValueError(f"Duplicate {name} ID")
    return set(ids)


class Template(Model):
    schema_version: Literal[1] = 1
    id: Identifier
    title: NonEmpty
    tags: list[NonEmpty]
    difficulty: Literal["introductory", "intermediate", "advanced"]
    original_problem: Problem
    assumptions: list[Assumption]
    methods: list[Method]
    correct_steps: Annotated[list[Step], Field(min_length=1)]
    conclusion: MathExpression
    allowed_perturbations: Annotated[list[PerturbationRule], Field(min_length=1)]
    expected_failure_mechanisms: list[NonEmpty]
    verification_rules: list[VerificationRule]
    explanation_fragments: list[ExplanationFragment]
    review: Review

    @model_validator(mode="after")
    def check_references(self) -> Self:
        conditions = unique_ids(self.original_problem.conditions, "condition")
        parameter_names = {item.name for item in self.original_problem.parameters}
        assumptions = unique_ids(self.assumptions, "assumption")
        methods = unique_ids(self.methods, "method")
        steps = unique_ids(self.correct_steps, "step")
        rules = unique_ids(self.verification_rules, "verification rule")
        unique_ids(self.allowed_perturbations, "perturbation rule")
        unique_ids(self.explanation_fragments, "explanation fragment")
        numbers = [step.number for step in self.correct_steps]
        if numbers != list(range(1, len(numbers) + 1)):
            raise ValueError("Step numbers must be sequential in stored order")

        def require_refs(refs: list[str], known: set[str], context: str) -> None:
            if set(refs) - known:
                raise ValueError(f"Unknown reference in {context}: {set(refs) - known}")

        for assumption in self.assumptions:
            require_refs(assumption.condition_ids, conditions, assumption.id)
        for method in self.methods:
            require_refs(method.assumption_ids, assumptions, method.id)
        for step in self.correct_steps:
            require_refs([step.method_id], methods, step.id)
            require_refs(step.assumption_ids, assumptions, step.id)
        for perturbation in self.allowed_perturbations:
            require_refs([perturbation.condition_id], conditions, perturbation.id)
            if perturbation.assumption_id is not None:
                require_refs([perturbation.assumption_id], assumptions, perturbation.id)
            unique_ids(perturbation.domain_choices, "domain choice")
            condition = next(item for item in self.original_problem.conditions if item.id == perturbation.condition_id)
            if perturbation.type == "domain":
                if not perturbation.domain_choices or condition.domain_binding is None or perturbation.allowed_values or perturbation.assumption_id:
                    raise ValueError("Domain rule needs a bound domain and choices only")
            elif perturbation.domain_choices:
                raise ValueError("Only domain rules may declare domain_choices")
        for condition in self.original_problem.conditions:
            if condition.parameter_name is not None:
                require_refs([condition.parameter_name], parameter_names, condition.id)
                parameter = next(item for item in self.original_problem.parameters if item.name == condition.parameter_name)
                predicate = condition.predicate
                if (predicate is None or predicate.relation != "eq"
                        or predicate.left.source != parameter.name
                        or predicate.right.source != parameter.value.source):
                    raise ValueError("Parameter condition must bind its declared parameter value")
        bindings = [item.parameter_name for item in self.original_problem.conditions if item.parameter_name is not None]
        if len(bindings) != len(set(bindings)):
            raise ValueError("A parameter must have only one condition binding")
        kinds = {"step": steps, "assumption": assumptions, "condition": conditions}
        for rule in self.verification_rules:
            for ref in rule.refs:
                require_refs([ref.id], kinds[ref.kind], rule.id)
        for step in self.correct_steps:
            if step.verification is not None:
                for ref in step.verification.affected_refs:
                    require_refs([ref.id], kinds[ref.kind], step.id)
        for fragment in self.explanation_fragments:
            require_refs(fragment.evidence_keys, rules, fragment.id)
            require_refs([match.rule_id for match in fragment.when], rules, fragment.id)
        spec = self.original_problem.computation
        if isinstance(spec, (EquationSpec, IntegralSpec, DerivativeAtPointSpec, StationaryPointSpec, LimitSpec)):
            require_refs([spec.variable], set(self.original_problem.variables), "computation variable")
        if isinstance(spec, FirstOrderIVPSpec):
            variables = self.original_problem.variables
            require_refs([spec.independent_variable, spec.dependent_variable], set(variables), "IVP variables")
            if any(variables[name] != "real" for name in (spec.independent_variable, spec.dependent_variable)) or spec.state_domain.number_system != "real":
                raise ValueError("IVP variables and state domain must be real")
        for assumption in self.assumptions:
            if assumption.interval is not None:
                require_refs([assumption.interval.variable], set(self.original_problem.variables), assumption.id)
            if assumption.check is not None:
                variable = assumption.check.equation.variable if isinstance(assumption.check, PrincipalSineCoverageCheck) else assumption.check.variable
                require_refs([variable], set(self.original_problem.variables), assumption.id)
        for rule in self.verification_rules:
            params = rule.parameters
            if isinstance(params, EquationTransform):
                require_refs([params.before.variable, params.after.variable], set(self.original_problem.variables), rule.id)
            elif isinstance(params, SubstitutionCheck):
                require_refs([params.transformed.variable], set(self.original_problem.variables), rule.id)
            elif isinstance(params, EvaluationCheck) and params.result_variable:
                require_refs([params.result_variable], set(self.original_problem.variables), rule.id)
            elif isinstance(params, SolveCandidatesCheck):
                require_refs([params.equation.variable], set(self.original_problem.variables), rule.id)
            elif isinstance(params, CandidateAcceptanceCheck):
                require_refs([params.original.variable, params.candidates_from.variable], set(self.original_problem.variables), rule.id)
                if params.original.variable != params.candidates_from.variable:
                    raise ValueError("Candidate acceptance variables must agree")
                if params.original != self.original_problem.computation:
                    raise ValueError("Candidate acceptance must reference the original problem equation")
            elif isinstance(params, PrincipalSineCheck):
                require_refs([params.equation.variable], set(self.original_problem.variables), rule.id)
                if params.equation != spec:
                    raise ValueError("Principal inverse must reference the actual problem equation")
            elif isinstance(params, (DerivativeIdentityCheck, DerivativePointSubstitutionCheck, StationaryValueCheck,
                                     DifferentiateLimitComponentsCheck, EvaluateLimitCheck, PrimitiveComponentsCheck, TwoPoleAnsatzCheck)):
                require_refs([params.variable], set(self.original_problem.variables), rule.id)
                if spec is not None and getattr(spec, "variable", None) != params.variable:
                    raise ValueError("Rule variable must match the actual computation variable")
            if isinstance(params, TwoPoleAnsatzCheck):
                if len(set(params.coefficient_names)) != 2 or params.variable in params.coefficient_names:
                    raise ValueError("Two distinct constant coefficient names are required")
                require_refs(list(params.coefficient_names), set(self.original_problem.variables), rule.id)
            if isinstance(params, (SqrtSubstitutionCheck, SqrtIntegrationCheck, RootRateCheck)):
                require_refs([params.root_variable], set(self.original_problem.variables), rule.id)
                if not isinstance(spec, FirstOrderIVPSpec) or params.root_variable in {spec.independent_variable, spec.dependent_variable}:
                    raise ValueError("Root substitution requires a distinct declared auxiliary variable")
        return self


class TemplateSummary(Model):
    id: Identifier
    title: str
    tags: list[str]
    difficulty: str


class PublicTemplate(TemplateSummary):
    original_problem: Problem
    allowed_perturbations: list[PerturbationRule]

    @classmethod
    def from_template(cls, template: Template) -> Self:
        return cls.model_validate({
            name: getattr(template, name) for name in cls.model_fields
        })


class Grade(StrEnum):
    CORRECT = "Correct"
    INCORRECT = "Incorrect"
    INDETERMINATE = "Indeterminate"


