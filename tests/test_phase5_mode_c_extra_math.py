"""Extra Mode C drafts: exact independent mathematics and existing content contracts.

No new runtime checker or mathematical model is used. Display claims are pinned
beside direct SymPy calculations, not parsed as LaTeX or judged by a new engine.
"""
import json
from pathlib import Path

import pytest
import sympy as sp

from app.challenges.grading import ChallengeNotFound, check_answer
from app.challenges.loader import load_challenges
from app.core.parsing import parse_math
from app.models.challenges import JudgeAIAnswer
from app.templates.loader import load_templates


DRAFT_DIRECTORY = Path(__file__).resolve().parents[1] / "docs/phase5/batch-05-mode-c-drafts"
EXPECTED_KEYS = {
    "sample-006": {("not_sound", "incorrect", "step-002", "premise-001", "lost_root")},
    "sample-007": {("not_sound", "incorrect", "step-003", "premise-001", "extraneous_root")},
    "sample-008": {("not_sound", "correct", "step-002", "premise-001", "zero_divisor")},
}


@pytest.fixture(scope="module")
def drafts():
    return load_challenges(
        load_templates(), DRAFT_DIRECTORY / "challenges", DRAFT_DIRECTORY
    )


def keys(sample):
    return {
        (item.derivation.value, item.conclusion.value, item.step_id,
         item.assumption_id, item.reason_category.value)
        for item in sample.rubric.accepted_answers
    }


@pytest.mark.parametrize("sample_id", EXPECTED_KEYS)
def test_existing_models_validate_complete_draft_rubrics_and_references(drafts, sample_id):
    sample = drafts.samples[sample_id]
    assert sample.review.status == "draft" and sample.review.reviewer is None
    assert sample.template_id is None
    assert len(sample.steps) == len(sample.annotations) == 3
    assert [item.id for item in sample.assumptions] == [
        "premise-001", "premise-002", "premise-003"
    ]
    assert all(step.verification is None for step in sample.steps)
    assert sample.rubric.reason_if_unknown is None
    assert keys(sample) == EXPECTED_KEYS[sample_id]
    first = next(item for item in sample.annotations if item.finding != "valid")
    assert first.step_id == next(iter(EXPECTED_KEYS[sample_id]))[2]
    assert first.assumption_ids == ["premise-001"]


def test_draft_configs_are_valid_and_unpublished(drafts):
    assert set(drafts.samples) == set(EXPECTED_KEYS)
    assert set(drafts.challenges) == {"practice-011", "practice-012", "practice-013"}
    assert {item.sample_id for item in drafts.challenges.values()} == set(EXPECTED_KEYS)
    assert drafts.public_summaries() == []
    for item in drafts.challenges.values():
        assert item.review.status == "draft" and item.review.reviewer is None
        assert drafts.public_detail(item.id) is None


@pytest.mark.parametrize("challenge_id", ["practice-011", "practice-012", "practice-013"])
def test_grading_rejects_drafts_without_running_symbolic_engine(drafts, challenge_id):
    challenge = drafts.challenges[challenge_id]
    sample = drafts.samples[challenge.sample_id]
    answer = JudgeAIAnswer(
        mode="C", challenge_id=challenge_id,
        **sample.rubric.accepted_answers[0].model_dump()
    )

    class NoExecution:
        def __getattr__(self, name):
            pytest.fail("A draft must not reach a computation executor")

    with pytest.raises(ChallengeNotFound):
        check_answer(drafts, answer, NoExecution())


def test_existing_correct_controls_and_public_bank_stay_available():
    published = load_challenges(load_templates())
    assert set(published.samples) == {f"sample-{number:03d}" for number in range(1, 6)}
    assert len(published.public_summaries()) == 10
    assert {sample.id for sample in published.samples.values() if sample.category == "correct"} == {
        "sample-001", "sample-002"
    }
    assert set(published.samples).isdisjoint(EXPECTED_KEYS)


def test_extra_categories_are_distinct_and_keep_incorrect_vs_correct_conclusions(drafts):
    assert {sample.category for sample in drafts.samples.values()} == {
        "flawed", "missing_condition", "wrong_derivation_right_answer"
    }
    assert {
        item.conclusion.value
        for sample in drafts.samples.values()
        for item in sample.rubric.accepted_answers
    } == {"correct", "incorrect"}


def test_006_displayed_principal_branch_and_first_false_equivalence(drafts):
    sample = drafts.samples["sample-006"]
    assert sample.problem.variables == {"x": "real"}
    assert [(p.relation, p.right.source) for p in sample.problem.domain_constraints] == [
        ("ge", "0"), ("lt", "2*pi")
    ]
    assert [step.output.latex for step in sample.steps] == [
        r"\alpha=\frac{\pi}{6}",
        r"\sin x=\sin\alpha\ \Longleftrightarrow\ x=\alpha=\frac{\pi}{6}",
        r"S_{\mathrm{original}}=\left\{\frac{\pi}{6}\right\}",
    ]
    x = sp.Symbol("x", real=True)
    spec = sample.problem.computation
    assert spec.kind == "equation" and spec.variable == "x"
    raw_residual = parse_math(spec.left.source, symbols={"x": x}) - parse_math(
        spec.right.source, symbols={"x": x}
    )
    residual = sp.simplify(raw_residual.doit())
    original = sp.solveset(residual, x, domain=sp.Interval.Ropen(0, 2 * sp.pi))
    principal = sp.asin(sp.Rational(1, 2))
    proposed = sp.FiniteSet(principal)
    assert principal == sp.pi / 6
    assert original == sp.FiniteSet(sp.pi / 6, 5 * sp.pi / 6)
    assert original - proposed == sp.FiniteSet(5 * sp.pi / 6)
    assert sp.simplify(residual.subs(x, 5 * sp.pi / 6).doit()) == 0
    assert sample.rubric.actual_conclusion.latex == (
        r"S_{\mathrm{original}}=\left\{\frac{\pi}{6},\frac{5\pi}{6}\right\}"
    )


@pytest.mark.parametrize("integer_period", [-1, 0, 1])
def test_006_periodic_families_and_interval_exhaustion(integer_period):
    k = sp.Integer(integer_period)
    candidates = (sp.pi / 6 + 2 * k * sp.pi, 5 * sp.pi / 6 + 2 * k * sp.pi)
    interval = sp.Interval.Ropen(0, 2 * sp.pi)
    for candidate in candidates:
        assert sp.sin(candidate) == sp.Rational(1, 2)
        assert bool(interval.contains(candidate)) is (integer_period == 0)
    # This checks adjacent periods; the full-family/exhaustiveness proof is in
    # the review document and independently confirmed by solveset above.


def test_007_candidate_is_valid_argument_but_not_principal(drafts):
    sample = drafts.samples["sample-007"]
    assert sample.problem.computation is None
    assert [(p.relation, p.right.source) for p in sample.problem.domain_constraints] == [
        ("gt", "-pi"), ("le", "pi")
    ]
    assert [step.output.latex for step in sample.steps] == [
        r"\alpha=\operatorname{Arg}(i)=\frac{\pi}{2},\qquad \beta=\operatorname{Arg}(-1)=\pi",
        r"\theta_0=\alpha+\beta=\frac{3\pi}{2},\qquad e^{i\theta_0}=-i",
        r"\operatorname{Arg}(-i)=\theta_0=\frac{3\pi}{2}",
    ]
    unwrapped = sp.arg(sp.I) + sp.arg(-1)
    principal_domain = sp.Interval.Lopen(-sp.pi, sp.pi)
    actual = sp.arg(-sp.I)
    assert unwrapped == 3 * sp.pi / 2
    assert sp.exp(sp.I * unwrapped) == -sp.I
    assert principal_domain.contains(unwrapped) is sp.S.false
    assert actual == -sp.pi / 2 == unwrapped - 2 * sp.pi
    assert principal_domain.contains(actual) is sp.S.true
    assert sp.simplify(parse_math(sample.rubric.actual_conclusion.source).doit()) == actual
    assert [item.finding for item in sample.annotations] == ["valid", "valid", "missing_condition"]


def test_007_unique_angle_equation_solution_on_stated_branch():
    theta = sp.Symbol("theta", real=True)
    branch = sp.Interval.Lopen(-sp.pi, sp.pi)
    # exp(i*theta)=-i is equivalent to simultaneous cos(theta)=0, sin(theta)=-1.
    cosine_roots = sp.solveset(sp.cos(theta), theta, domain=branch)
    sine_roots = sp.solveset(sp.sin(theta) + 1, theta, domain=branch)
    assert cosine_roots & sine_roots == sp.FiniteSet(-sp.pi / 2)
    assert branch.contains(-sp.pi) is sp.S.false
    assert branch.contains(sp.pi) is sp.S.true
    assert sp.arg(-1) == sp.pi


def test_008_norms_prove_nonexistence_but_do_not_define_normalization(drafts):
    sample = drafts.samples["sample-008"]
    assert sample.problem.expression.latex == r"u=(0,0,0),\qquad v=(1,1,0)"
    assert [step.output.latex for step in sample.steps] == [
        r"\|u\|=0,\qquad \|v\|=\sqrt2",
        r"\frac{u}{\|u\|}=\left(\frac00,\frac00,\frac00\right)=(0,0,0)",
        r"\|u\|=0\ \Longrightarrow\ \angle(u,v)\text{ is undefined}",
    ]
    assert sample.steps[2].input.latex == r"\|u\|=0"
    assert [item.finding for item in sample.annotations] == ["valid", "invalid", "valid"]
    assert sample.claimed_conclusion.latex == sample.rubric.actual_conclusion.latex
    u, v = (0, 0, 0), (1, 1, 0)
    norm_u_sq = sum(component**2 for component in u)
    norm_v_sq = sum(component**2 for component in v)
    assert (norm_u_sq, norm_v_sq) == (0, 2)
    assert (sp.sqrt(norm_u_sq), sp.sqrt(norm_v_sq)) == (0, sp.sqrt(2))
    denominator = sp.sqrt(norm_u_sq) * sp.sqrt(norm_v_sq)
    assert denominator == 0
    zero_over_zero = sp.Mul(sp.Integer(0), sp.Pow(0, -1, evaluate=False), evaluate=False)
    assert zero_over_zero.doit() is sp.nan
    assert zero_over_zero.doit() != 0
    # Do not turn nan into an angle value; the mathematical domain excludes u=0.


def test_008_zero_dot_product_does_not_define_a_right_angle():
    theta = sp.Symbol("theta", real=True)
    u, v = (0, 0, 0), (1, 1, 0)
    dot = sum(a * b for a, b in zip(u, v, strict=True))
    denominator = sp.sqrt(sum(a**2 for a in u)) * sp.sqrt(sum(b**2 for b in v))
    assert dot == denominator == 0
    assert sp.simplify((dot - denominator * sp.cos(theta)).doit()) == 0
    # The identity holds for every theta and selects no unique angle.


def test_draft_json_ids_and_configs_are_self_contained():
    paths = sorted(DRAFT_DIRECTORY.glob("sample-*.json"))
    assert len(paths) == 3
    for path in paths:
        raw = json.loads(path.read_text(encoding="utf-8"))
        assert path.stem == raw["id"]
        assert raw["review"]["status"] == "draft"
        assert raw["review"]["reviewer"] is None
        assert raw["template_id"] is None
