"""Phase 4 authoring, request and public contracts. No grading is performed here."""
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from app.models.analysis import AnalysisResponse
from app.models.domain import (
    Assumption, Condition, Evidence, EvidenceMatch, Grade, Identifier, MathExpression,
    Method, Model, NonEmpty, Parameter, Perturbation, PerturbationType, Predicate,
    Problem, Review, Step, TransformationKind, unique_ids,
    DomainChoice,
)


class ReasonCategory(StrEnum):
    NO_FLAW = "no_flaw"
    ZERO_DIVISOR = "zero_divisor"
    IMPROPER_ENDPOINT = "improper_endpoint"
    MISSING_SIGN_CONDITION = "missing_sign_condition"
    IRREVERSIBLE_SQUARING = "irreversible_squaring"
    EXTRANEOUS_ROOT = "extraneous_root"
    LOST_ROOT = "lost_root"
    ARITHMETIC_ERROR = "arithmetic_error"


class DerivationJudgement(StrEnum):
    SOUND = "sound"
    NOT_SOUND = "not_sound"


class ConclusionJudgement(StrEnum):
    CORRECT = "correct"
    INCORRECT = "incorrect"
    NOT_ESTABLISHED = "not_established"


class ChallengeGoal(StrEnum):
    INVALIDATE_ORIGINAL_DERIVATION = "invalidate_original_derivation"
    CHANGE_CONCLUSION = "change_conclusion"


class FlawSelection(Model):
    step_id: Identifier | None
    assumption_id: Identifier | None
    reason_category: ReasonCategory

    @model_validator(mode="after")
    def selection_shape(self) -> Self:
        if self.reason_category == ReasonCategory.NO_FLAW:
            if self.step_id is not None or self.assumption_id is not None:
                raise ValueError("no_flaw requires null step and assumption")
        elif self.step_id is None:
            raise ValueError("A flaw selection requires a step")
        return self


class SampleJudgement(FlawSelection):
    derivation: DerivationJudgement
    conclusion: ConclusionJudgement

    @model_validator(mode="after")
    def judgement_shape(self) -> Self:
        if (self.derivation == DerivationJudgement.SOUND) != (self.reason_category == ReasonCategory.NO_FLAW):
            raise ValueError("Only sound derivations use no_flaw")
        return self


class AnswerBase(Model):
    challenge_id: Identifier
    free_text: Annotated[str, Field(max_length=4000)] | None = None


class FindFlawAnswer(AnswerBase, FlawSelection):
    mode: Literal["A"]


class BreakMethodAnswer(AnswerBase):
    mode: Literal["B"]
    perturbation: Perturbation


class JudgeAIAnswer(AnswerBase, SampleJudgement):
    mode: Literal["C"]


ChallengeAnswer = Annotated[
    FindFlawAnswer | BreakMethodAnswer | JudgeAIAnswer, Field(discriminator="mode")
]


def require_review_identity(review: Review) -> None:
    if review.status == "reviewed" and review.reviewer is None:
        raise ValueError("Reviewed content requires a named reviewer")


class EvidenceBoundAnswer(Model):
    """One complete answer tuple; all evidence matches in this entry are required."""
    answer: FlawSelection
    evidence_matches: Annotated[list[EvidenceMatch], Field(min_length=1)]


class SampleRubric(Model):
    accepted_answers: list[SampleJudgement]
    # Empty keys mean genuinely unestablished grading, never an incorrect user.
    reason_if_unknown: NonEmpty | None = None
    mathematical_basis: Annotated[list[NonEmpty], Field(min_length=1)]
    actual_conclusion: MathExpression | None = None
    remediation: NonEmpty | None = None

    @model_validator(mode="after")
    def known_or_unknown(self) -> Self:
        if bool(self.accepted_answers) == (self.reason_if_unknown is not None):
            raise ValueError("Rubric needs either accepted answers or an explicit unknown reason")
        return self


class SampleAnnotation(Model):
    """Private authoring assertions, pending the enclosing sample's review."""
    step_id: Identifier
    finding: Literal["valid", "missing_condition", "invalid"]
    assumption_ids: list[Identifier] = Field(default_factory=list)
    basis: NonEmpty


class AIDerivationSample(Model):
    id: Identifier
    title: NonEmpty
    template_id: Identifier | None = None  # provenance only, never the sample's verdict
    problem: Problem
    assumptions: list[Assumption]
    methods: Annotated[list[Method], Field(min_length=1)]
    steps: Annotated[list[Step], Field(min_length=1)]
    claimed_conclusion: MathExpression
    category: Literal["correct", "missing_condition", "wrong_derivation_right_answer", "flawed"]
    annotations: list[SampleAnnotation]
    rubric: SampleRubric
    review: Review

    @model_validator(mode="after")
    def references(self) -> Self:
        conditions = unique_ids(self.problem.conditions, "condition")
        parameters = {item.name: item for item in self.problem.parameters}
        assumptions = unique_ids(self.assumptions, "assumption")
        methods = unique_ids(self.methods, "method")
        steps = unique_ids(self.steps, "step")
        if [step.number for step in self.steps] != list(range(1, len(self.steps) + 1)):
            raise ValueError("Step numbers must be sequential in stored order")

        def refs(values, known, context):
            if set(values) - known:
                raise ValueError(f"Unknown reference in {context}: {set(values) - known}")

        bindings = []
        for condition in self.problem.conditions:
            if condition.parameter_name is None:
                continue
            refs([condition.parameter_name], parameters.keys(), "parameter condition")
            parameter = parameters[condition.parameter_name]
            predicate = condition.predicate
            if (predicate is None or predicate.relation != "eq"
                    or predicate.left.source != parameter.name
                    or predicate.right.source != parameter.value.source):
                raise ValueError("Parameter condition must bind its declared parameter value")
            bindings.append(condition.parameter_name)
        if len(bindings) != len(set(bindings)):
            raise ValueError("A parameter must have only one condition binding")
        for assumption in self.assumptions:
            refs(assumption.condition_ids, conditions, assumption.id)
        for method in self.methods:
            refs(method.assumption_ids, assumptions, method.id)
        for step in self.steps:
            refs([step.method_id], methods, step.id)
            refs(step.assumption_ids, assumptions, step.id)
            # Sample findings live in the private annotations, not runtime verdicts.
            if step.verification is not None:
                raise ValueError("Sample steps must not carry runtime verification")
        annotated = [item.step_id for item in self.annotations]
        if len(annotated) != len(set(annotated)) or set(annotated) != steps:
            raise ValueError("Each sample step needs exactly one private annotation")
        for item in self.annotations:
            refs(item.assumption_ids, assumptions, item.step_id)
        for answer in self.rubric.accepted_answers:
            refs([answer.step_id] if answer.step_id else [], steps, "rubric step")
            refs([answer.assumption_id] if answer.assumption_id else [], assumptions, "rubric assumption")
        require_review_identity(self.review)
        return self


class ChallengeBase(Model):
    id: Identifier
    title: NonEmpty
    prompt: NonEmpty
    review: Review

    @model_validator(mode="after")
    def review_identity(self) -> Self:
        require_review_identity(self.review)
        return self


class FindFlawChallenge(ChallengeBase):
    mode: Literal["A"]
    template_id: Identifier
    perturbation: Perturbation
    accepted_answers: Annotated[list[EvidenceBoundAnswer], Field(min_length=1)]


class BreakMethodChallenge(ChallengeBase):
    mode: Literal["B"]
    template_id: Identifier
    goal: ChallengeGoal


class JudgeAIChallenge(ChallengeBase):
    mode: Literal["C"]
    sample_id: Identifier


Challenge = Annotated[
    FindFlawChallenge | BreakMethodChallenge | JudgeAIChallenge, Field(discriminator="mode")
]


class ChallengeSummary(Model):
    id: Identifier
    title: NonEmpty
    mode: Literal["A", "B", "C"]


class ChallengeProblem(Model):
    """Stated mathematics only; excludes outcome status and computation specs."""
    statement: NonEmpty
    expression: MathExpression
    goal: NonEmpty
    variables: dict[Identifier, Literal["real", "complex", "integer"]]
    parameters: list[Parameter]
    conditions: list[Condition]
    domain_constraints: list[Predicate]


class PresentedStep(Model):
    id: Identifier
    number: int
    input: MathExpression
    output: MathExpression
    method_id: Identifier
    # This is the displayed derivation's claim, not a verified judgement.
    transformation_kind: TransformationKind


class PresentedMethod(Model):
    id: Identifier
    name: NonEmpty


class AssumptionOption(Model):
    id: Identifier
    label: NonEmpty


class ReasonOption(Model):
    id: ReasonCategory
    label: NonEmpty


class PublicPerturbationRule(Model):
    id: Identifier
    condition_id: Identifier
    type: PerturbationType
    description: NonEmpty
    allowed_values: list[MathExpression]
    domain_choices: list[DomainChoice] = Field(default_factory=list)


class PublicChallengeBase(ChallengeSummary):
    prompt: NonEmpty
    problem: ChallengeProblem
    steps: list[PresentedStep]
    methods: list[PresentedMethod]


class PublicFindFlawChallenge(PublicChallengeBase):
    mode: Literal["A"]
    changed_problem: ChallengeProblem
    perturbation: Perturbation
    assumption_options: list[AssumptionOption]
    reason_options: list[ReasonOption]


class PublicBreakMethodChallenge(PublicChallengeBase):
    mode: Literal["B"]
    template_id: Identifier
    goal: ChallengeGoal
    allowed_perturbations: list[PublicPerturbationRule]


class PublicJudgeAIChallenge(PublicChallengeBase):
    mode: Literal["C"]
    claimed_conclusion: MathExpression
    assumption_options: list[AssumptionOption]
    reason_options: list[ReasonOption]


PublicChallenge = Annotated[
    PublicFindFlawChallenge | PublicBreakMethodChallenge | PublicJudgeAIChallenge,
    Field(discriminator="mode"),
]


class ReviewedSampleFeedback(Model):
    """Post-submission review findings; never presented as live engine analysis."""
    derivation: DerivationJudgement | None
    conclusion: ConclusionJudgement | None
    first_flaw_step_id: Identifier | None
    annotations: list[SampleAnnotation]
    actual_conclusion: MathExpression | None
    reason_if_unknown: NonEmpty | None = None


class ChallengeFeedback(Model):
    challenge_id: Identifier
    mode: Literal["A", "B", "C"]
    grade: Grade
    explanation: NonEmpty
    evidence: list[Evidence]
    remediation: NonEmpty | None = None
    analysis: AnalysisResponse | None = None
    sample_feedback: ReviewedSampleFeedback | None = None
    free_text: str | None = None  # echoed only; no persistence or semantic scoring
