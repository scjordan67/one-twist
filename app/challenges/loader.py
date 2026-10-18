"""Validate draft and reviewed content. Public access exposes reviewed items only."""
from dataclasses import dataclass
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from app.engine.perturbation import construct_problem
from app.models.challenges import (
    AIDerivationSample, AssumptionOption, Challenge, ChallengeSummary,
    FindFlawChallenge, JudgeAIChallenge, PresentedMethod, PresentedStep,
    ChallengeProblem, PublicBreakMethodChallenge, PublicChallenge,
    PublicFindFlawChallenge, PublicJudgeAIChallenge, PublicPerturbationRule,
    ReasonCategory, ReasonOption,
)
from app.models.domain import Template
from app.models.domain import EquationSpec, IntegralSpec, DerivativeAtPointSpec, StationaryPointSpec, LimitSpec
from app.templates.loader import validate_expressions

DATA_DIRECTORY = Path(__file__).parent / "data"
CHALLENGE_DIRECTORY = DATA_DIRECTORY / "challenges"
SAMPLE_DIRECTORY = DATA_DIRECTORY / "samples"
CHALLENGE_ADAPTER = TypeAdapter(Challenge)

# Identical choices for all samples; selection is never filtered by the answer key.
REASON_LABELS = {
    ReasonCategory.NO_FLAW: "No flaw in the presented derivation",
    ReasonCategory.ZERO_DIVISOR: "Division by a zero divisor",
    ReasonCategory.IMPROPER_ENDPOINT: "A singular endpoint requires an improper-integral treatment",
    ReasonCategory.MISSING_SIGN_CONDITION: "A required sign condition is missing",
    ReasonCategory.IRREVERSIBLE_SQUARING: "Squaring was used as an equivalence without the reverse implication",
    ReasonCategory.EXTRANEOUS_ROOT: "Extra candidates were accepted as original solutions",
    ReasonCategory.LOST_ROOT: "A transformation loses original solutions",
    ReasonCategory.ARITHMETIC_ERROR: "An arithmetic operation is incorrect",
}


class ChallengeLoadError(ValueError):
    pass


def _project(value, dto):
    # Explicit DTO fields, never an exclude-list over private authoring models.
    return dto.model_validate(value.model_dump(include=set(dto.model_fields)))


def _presentation(problem, steps, methods):
    return dict(
        problem=_project(problem, ChallengeProblem),
        steps=[_project(step, PresentedStep) for step in steps],
        methods=[_project(method, PresentedMethod) for method in methods],
    )


def _options(assumptions):
    return dict(
        assumption_options=[AssumptionOption(id=item.id, label=item.description) for item in assumptions],
        reason_options=[ReasonOption(id=key, label=label) for key, label in REASON_LABELS.items()],
    )


@dataclass
class ChallengeBank:
    templates: dict[str, Template]
    samples: dict[str, AIDerivationSample]
    challenges: dict[str, Challenge]

    def public_summaries(self) -> list[ChallengeSummary]:
        return [_project(item, ChallengeSummary) for item in self.challenges.values() if item.review.status == "reviewed"]

    def public_detail(self, challenge_id: str) -> PublicChallenge | None:
        challenge = self.challenges.get(challenge_id)
        if challenge is None or challenge.review.status != "reviewed":
            return None
        common = dict(id=challenge.id, title=challenge.title, mode=challenge.mode, prompt=challenge.prompt)
        if isinstance(challenge, JudgeAIChallenge):
            sample = self.samples[challenge.sample_id]
            return PublicJudgeAIChallenge(
                **common, **_presentation(sample.problem, sample.steps, sample.methods),
                **_options(sample.assumptions), claimed_conclusion=sample.claimed_conclusion,
            )
        template = self.templates[challenge.template_id]
        common.update(_presentation(template.original_problem, template.correct_steps, template.methods))
        if isinstance(challenge, FindFlawChallenge):
            changed = construct_problem(template, challenge.perturbation)
            return PublicFindFlawChallenge(
                **common, **_options(template.assumptions), perturbation=changed.perturbation,
                changed_problem=_project(changed.problem, ChallengeProblem),
            )
        return PublicBreakMethodChallenge(
            **common, template_id=template.id, goal=challenge.goal,
            allowed_perturbations=[_project(rule, PublicPerturbationRule) for rule in template.allowed_perturbations],
        )


def _read_models(directory: Path, adapter) -> dict:
    if not directory.is_dir():
        raise ChallengeLoadError(f"Content directory does not exist: {directory}")
    models = {}
    for path in sorted(directory.glob("*.json")):
        try:
            model = adapter.validate_json(path.read_text(encoding="utf-8"))
        except (ValidationError, OSError) as exc:
            raise ChallengeLoadError(f"Invalid content {path.name}: {exc}") from exc
        if model.id in models:
            raise ChallengeLoadError(f"Duplicate content ID: {model.id}")
        models[model.id] = model
    if not models:
        raise ChallengeLoadError(f"Content directory contains no JSON files: {directory}")
    return models


def _validate_find_flaw(challenge: FindFlawChallenge, template: Template) -> None:
    construct_problem(template, challenge.perturbation)  # canonical rule/condition/value checks only
    steps = {item.id: item for item in template.correct_steps}
    assumptions = {item.id for item in template.assumptions}
    rules = {item.id: item for item in template.verification_rules}
    evidence_ids = rules.keys() | {f"assumption-{item}" for item in assumptions}
    seen = set()
    for entry in challenge.accepted_answers:
        answer = entry.answer
        if answer.step_id not in steps:
            raise ValueError("Unknown reference in Mode A answer step")
        if answer.assumption_id is not None and answer.assumption_id not in steps[answer.step_id].assumption_ids:
            raise ValueError("Unknown reference in Mode A step's assumptions")
        if any(match.rule_id not in evidence_ids for match in entry.evidence_matches):
            raise ValueError("Unknown reference in Mode A evidence matches")
        if not any(
            match.rule_id in rules and any(ref.kind == "step" and ref.id == answer.step_id for ref in rules[match.rule_id].refs)
            for match in entry.evidence_matches
        ):
            raise ValueError("Mode A answer needs evidence from a rule bound to its step")
        key = (answer.step_id, answer.assumption_id, answer.reason_category)
        if key in seen:
            raise ValueError("Duplicate Mode A answer tuple")
        seen.add(key)


def load_challenges(
    templates: dict[str, Template],
    challenge_directory: Path = CHALLENGE_DIRECTORY,
    sample_directory: Path = SAMPLE_DIRECTORY,
) -> ChallengeBank:
    """Load drafts for audit, but never publish them. Does not analyze or grade."""
    samples = _read_models(sample_directory, TypeAdapter(AIDerivationSample))
    challenges = _read_models(challenge_directory, CHALLENGE_ADAPTER)
    for sample in samples.values():
        try:
            if sample.template_id is not None and sample.template_id not in templates:
                raise ValueError("Unknown reference in sample template provenance")
            symbols = set(sample.problem.variables) | {item.name for item in sample.problem.parameters}
            if isinstance(sample.problem.computation, (EquationSpec, IntegralSpec, DerivativeAtPointSpec, StationaryPointSpec, LimitSpec)) and sample.problem.computation.variable not in sample.problem.variables:
                raise ValueError("Unknown reference in sample computation variable")
            for assumption in sample.assumptions:
                if assumption.interval and assumption.interval.variable not in sample.problem.variables:
                    raise ValueError("Unknown reference in sample assumption interval")
            validate_expressions(sample, symbols)
        except ValueError as exc:
            raise ChallengeLoadError(f"Invalid sample {sample.id}: {exc}") from exc
    for challenge in challenges.values():
        try:
            if isinstance(challenge, JudgeAIChallenge):
                if challenge.sample_id not in samples:
                    raise ValueError("Unknown reference in challenge sample")
                if challenge.review.status == "reviewed" and samples[challenge.sample_id].review.status != "reviewed":
                    raise ValueError("Reviewed challenge cannot publish an unreviewed sample")
            else:
                if challenge.template_id not in templates:
                    raise ValueError("Unknown reference in challenge template")
                if isinstance(challenge, FindFlawChallenge):
                    _validate_find_flaw(challenge, templates[challenge.template_id])
        except ValueError as exc:
            raise ChallengeLoadError(f"Invalid challenge {challenge.id}: {exc}") from exc
    return ChallengeBank(templates=templates, samples=samples, challenges=challenges)
