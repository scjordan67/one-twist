"""Evidence-gated A/B grading; C uses an explicitly reviewed rubric only."""
from app.challenges.loader import ChallengeBank
from app.core.isolation import ComputationExecutor
from app.engine.service import analyze_isolated
from app.models.analysis import AnalysisResponse
from app.models.challenges import (
    BreakMethodAnswer, ChallengeAnswer, ChallengeFeedback, ChallengeGoal,
    FindFlawAnswer, FlawSelection, JudgeAIAnswer, ReviewedSampleFeedback, SampleJudgement,
)
from app.models.domain import Evidence, Grade, ValidityLabel as Label


class ChallengeNotFound(ValueError):
    pass


class InvalidChallengeAnswer(ValueError):
    pass


def _selection(answer):
    return FlawSelection.model_validate(answer.model_dump(include=set(FlawSelection.model_fields)))


def _evidence(analysis: AnalysisResponse) -> list[Evidence]:
    report = analysis.report
    items = [ev for dim in [*report.step.values(), report.method, report.conclusion] for ev in dim.evidence]
    items.extend(item.evidence for item in report.assumptions.values())
    # Preserve evidence order, removing repeated references from merged dimensions.
    return list({(ev.rule_id, ev.outcome, ev.summary, ev.origin): ev for ev in items}.values())


def _grade_a(challenge, answer, analysis, evidence):
    first = analysis.report.first_invalid_step_id
    if first is None:
        return Grade.INDETERMINATE, "The first invalid step has not been established by the available checks."
    computed = {(ev.rule_id, ev.outcome) for ev in evidence if ev.origin == "computed"}
    entries = [entry for entry in challenge.accepted_answers if entry.answer.step_id == first]
    supported = [entry for entry in entries if all((match.rule_id, match.outcome) in computed for match in entry.evidence_matches)]
    if any(_selection(answer) == entry.answer for entry in supported):
        return Grade.CORRECT, "Your complete selection matches the established first invalid step and all of its required computed evidence."
    if not entries or len(supported) != len(entries):
        return Grade.INDETERMINATE, "The computed evidence does not establish the complete reviewed answer standard."
    return Grade.INCORRECT, "The first invalid step and its supporting premise/reason are established by the computed evidence. Your complete selection does not match a supported answer."


def _grade_b(challenge, analysis):
    report = analysis.report
    if challenge.goal == ChallengeGoal.CHANGE_CONCLUSION:
        achieved = report.comparison.changed if report.comparison else None
        description = "change the conclusion"
    else:
        steps = list(report.step.values())
        achieved = True if any(Label.INVALID_STEP in step.labels for step in steps) else (
            False if steps and all(step.labels == {Label.VALID} for step in steps) else None
        )
        description = "invalidate the original derivation as written"
    if achieved is None:
        return Grade.INDETERMINATE, f"The checks have not established whether this change meets the goal: {description}."
    return (Grade.CORRECT if achieved else Grade.INCORRECT,
            f"This change {'meets' if achieved else 'does not meet'} the stated goal: {description}. "
            "Method applicability and conclusion validity are reported independently below.")


def check_answer(bank: ChallengeBank, answer: ChallengeAnswer, executor: ComputationExecutor) -> ChallengeFeedback:
    challenge = bank.challenges.get(answer.challenge_id)
    if challenge is None or challenge.review.status != "reviewed":
        raise ChallengeNotFound("Challenge not found")
    if answer.mode != challenge.mode:
        raise InvalidChallengeAnswer("Answer mode must match the selected challenge")
    public = bank.public_detail(challenge.id)
    if isinstance(answer, (FindFlawAnswer, JudgeAIAnswer)):
        if answer.step_id is not None and answer.step_id not in {step.id for step in public.steps}:
            raise InvalidChallengeAnswer("Step is not an offered choice")
        if answer.assumption_id is not None and answer.assumption_id not in {item.id for item in public.assumption_options}:
            raise InvalidChallengeAnswer("Premise is not an offered choice")
    common = dict(challenge_id=challenge.id, mode=challenge.mode, free_text=answer.free_text)
    if isinstance(answer, JudgeAIAnswer):
        sample = bank.samples[challenge.sample_id]
        if sample.review.status != "reviewed":
            raise ChallengeNotFound("Reviewed sample not found")
        rubric = sample.rubric
        judgement = SampleJudgement.model_validate(answer.model_dump(include=set(SampleJudgement.model_fields)))
        known = rubric.reason_if_unknown is None
        grade = (Grade.CORRECT if judgement in rubric.accepted_answers else Grade.INCORRECT) if known else Grade.INDETERMINATE
        standard = rubric.accepted_answers[0] if known else None
        return ChallengeFeedback(
            **common, grade=grade,
            explanation=("Your full judgement matches the reviewed standard." if grade == Grade.CORRECT else
                         "Your full judgement differs from the reviewed standard." if known else rubric.reason_if_unknown)
                        + " This feedback comes from human review, not live symbolic verification of this derivation.",
            evidence=[Evidence(rule_id="sample-review", origin="author_reviewed", summary=basis) for basis in rubric.mathematical_basis],
            remediation=rubric.remediation,
            sample_feedback=ReviewedSampleFeedback(
                derivation=standard.derivation if standard else None,
                conclusion=standard.conclusion if standard else None,
                first_flaw_step_id=standard.step_id if standard else None,
                annotations=sample.annotations if known else [], actual_conclusion=rubric.actual_conclusion,
                reason_if_unknown=rubric.reason_if_unknown,
            ),
        )
    template = bank.templates[challenge.template_id]
    if isinstance(answer, BreakMethodAnswer):
        if answer.perturbation.template_id != template.id:
            raise InvalidChallengeAnswer("Perturbation must use the challenge's template")
        perturbation = answer.perturbation
    else:
        perturbation = challenge.perturbation
    analysis = analyze_isolated(template, perturbation, executor)
    evidence = _evidence(analysis)
    grade, explanation = _grade_a(challenge, answer, analysis, evidence) if isinstance(answer, FindFlawAnswer) else _grade_b(challenge, analysis)
    return ChallengeFeedback(**common, grade=grade, explanation=explanation, evidence=evidence,
                             remediation=analysis.report.method.remediation, analysis=analysis)
