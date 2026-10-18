"""Authoring and publication contracts, independent of runtime grading."""
import copy
import json
from collections import Counter

import pytest
from pydantic import TypeAdapter, ValidationError

from app.challenges.loader import (
    CHALLENGE_DIRECTORY, SAMPLE_DIRECTORY, ChallengeLoadError, load_challenges,
)
from app.models.challenges import (
    AIDerivationSample, Challenge, ChallengeAnswer, ChallengeFeedback, SampleRubric,
)
from app.models.domain import DimensionResult, Review, WellFormedness
from app.templates.loader import load_templates

ANSWER = TypeAdapter(ChallengeAnswer)
CONFIG = TypeAdapter(Challenge)


@pytest.fixture
def bank():
    return load_challenges(load_templates())


@pytest.fixture
def content_dirs(tmp_path):
    samples, challenges = tmp_path / "samples", tmp_path / "challenges"
    samples.mkdir()
    challenges.mkdir()
    for origin, target in [(SAMPLE_DIRECTORY, samples), (CHALLENGE_DIRECTORY, challenges)]:
        for path in origin.glob("*.json"):
            (target / path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return challenges, samples


def mutate(directory, id, edit):
    path = directory / f"{id}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    edit(data)
    path.write_text(json.dumps(data), encoding="utf-8")


def load_dirs(dirs):
    return load_challenges(load_templates(), *dirs)


def published_fixture(bank):
    """In-memory test-only review identity; never changes content review records."""
    bank = copy.deepcopy(bank)
    for content in [*bank.samples.values(), *bank.challenges.values()]:
        content.review = Review(status="reviewed", reviewer="TEST FIXTURE ONLY", basis="Synthetic publication test, not a content approval.")
    return bank


def answers(bank):
    a = bank.challenges["practice-001"].accepted_answers[0].answer.model_dump(mode="json")
    return {
        "A": dict(mode="A", challenge_id="practice-001", **a),
        "B": dict(mode="B", challenge_id="practice-003", perturbation=bank.challenges["practice-001"].perturbation.model_dump(mode="json")),
        "C": dict(mode="C", challenge_id="practice-006", **bank.samples["sample-001"].rubric.accepted_answers[0].model_dump(mode="json")),
    }


def test_independently_reviewed_content_and_all_four_sample_categories_are_present(bank):
    assert len(bank.challenges) == 10
    assert Counter(item.mode for item in bank.challenges.values()) == {"A": 2, "B": 3, "C": 5}
    assert Counter(item.category for item in bank.samples.values()) == {
        "correct": 2, "missing_condition": 1, "wrong_derivation_right_answer": 1, "flawed": 1,
    }
    assert all(item.review.status == "reviewed" and item.review.reviewer == "Claude Code" for item in [*bank.samples.values(), *bank.challenges.values()])
    assert len(bank.public_summaries()) == 10
    assert all(bank.public_detail(id) is not None for id in bank.challenges)
    assert {id for id, item in bank.templates.items() if item.review.status == "draft"} == {"integral-endpoint"}
    assert bank.public_detail("missing") is None


@pytest.mark.parametrize("mode", ["A", "B", "C"])
def test_mode_specific_answers_roundtrip_and_optional_text_is_only_text(bank, mode):
    data = answers(bank)[mode]
    data["free_text"] = "__import__('os').system('this is prose, not executed')"
    answer = ANSWER.validate_python(data)
    assert ANSWER.validate_json(answer.model_dump_json()) == answer


@pytest.mark.parametrize("mode,extra", [
    ("A", {"perturbation": {}}), ("A", {"derivation": "sound"}),
    ("B", {"step_id": "step-001"}), ("B", {"reason_category": "no_flaw"}),
    ("C", {"perturbation": {}}),
    ("A", {"grade": "Correct"}), ("B", {"evidence": []}), ("C", {"rubric": {}}),
])
def test_cross_mode_fields_and_client_verdicts_are_forbidden(bank, mode, extra):
    with pytest.raises(ValidationError, match="Extra inputs"):
        ANSWER.validate_python({**answers(bank)[mode], **extra})


@pytest.mark.parametrize("mode,field", [("A", "step_id"), ("B", "perturbation"), ("C", "derivation"), ("C", "conclusion")])
def test_required_answer_fields_cannot_be_omitted(bank, mode, field):
    data = answers(bank)[mode]
    del data[field]
    with pytest.raises(ValidationError, match="Field required"):
        ANSWER.validate_python(data)


def test_sound_sample_needs_no_fake_flaw_and_flawed_answers_need_a_step(bank):
    sound = answers(bank)["C"]
    assert sound["reason_category"] == "no_flaw"
    assert sound["step_id"] is sound["assumption_id"] is None
    with pytest.raises(ValidationError, match="null step"):
        ANSWER.validate_python({**sound, "step_id": "step-001"})
    with pytest.raises(ValidationError, match="requires a step"):
        ANSWER.validate_python({**sound, "derivation": "not_sound", "reason_category": "missing_sign_condition"})
    with pytest.raises(ValidationError, match="Only sound"):
        ANSWER.validate_python({**sound, "derivation": "not_sound"})


def test_unknown_mode_and_oversized_free_text_are_rejected(bank):
    with pytest.raises(ValidationError, match="union_tag_invalid"):
        ANSWER.validate_python({**answers(bank)["A"], "mode": "D"})
    data = {**answers(bank)["A"], "free_text": "x" * 4000}
    assert len(ANSWER.validate_python(data).free_text) == 4000
    with pytest.raises(ValidationError, match="4000"):
        ANSWER.validate_python({**data, "free_text": "x" * 4001})


def test_rubric_unknown_is_explicit_and_not_a_negative_answer_key(bank):
    data = bank.samples["sample-001"].rubric.model_dump(mode="json")
    with pytest.raises(ValidationError, match="either accepted answers"):
        SampleRubric.model_validate({**data, "accepted_answers": []})
    with pytest.raises(ValidationError, match="either accepted answers"):
        SampleRubric.model_validate({**data, "reason_if_unknown": "Not established"})
    unknown = SampleRubric.model_validate({**data, "accepted_answers": [], "actual_conclusion": None, "reason_if_unknown": "Audit has not established a standard."})
    assert unknown.accepted_answers == []
    feedback = ChallengeFeedback(challenge_id="practice-001", mode="A", grade="Indeterminate", explanation="First invalid step was not established.", evidence=[])
    assert feedback.grade.value == "Indeterminate"


@pytest.mark.parametrize("kind", ["sample", "challenge"])
def test_reviewed_content_requires_a_named_reviewer(bank, kind):
    model = bank.samples["sample-001"] if kind == "sample" else bank.challenges["practice-001"]
    data = model.model_dump(mode="json")
    data["review"]["status"] = "reviewed"
    data["review"]["reviewer"] = None
    adapter = TypeAdapter(AIDerivationSample) if kind == "sample" else CONFIG
    with pytest.raises(ValidationError, match="named reviewer"):
        adapter.validate_python(data)


@pytest.mark.parametrize("edit", [
    lambda d: d["methods"][0].update(assumption_ids=["missing"]),
    lambda d: d["steps"][0].update(method_id="missing"),
    lambda d: d["steps"][0].update(assumption_ids=["missing"]),
    lambda d: d["steps"][0].update(number=2),
    lambda d: d["steps"][0].update(verification={"labels": ["Valid"]}),
    lambda d: d["assumptions"][0].update(condition_ids=["missing"]),
    lambda d: d["annotations"][0].update(step_id="missing"),
    lambda d: d["annotations"][0].update(assumption_ids=["missing"]),
    lambda d: d["annotations"].pop(),
    lambda d: d["rubric"]["accepted_answers"][0].update(step_id="missing", reason_category="zero_divisor", derivation="not_sound"),
    lambda d: d["rubric"]["accepted_answers"][0].update(step_id="step-001", assumption_id="missing", reason_category="zero_divisor", derivation="not_sound"),
    lambda d: d["problem"]["conditions"][0].update(parameter_name="missing"),
    lambda d: d["problem"]["conditions"][0]["predicate"]["right"].update(source="3"),
])
def test_sample_reference_and_shape_errors_are_rejected(bank, edit):
    data = bank.samples["sample-001"].model_dump(mode="json")
    edit(data)
    with pytest.raises(ValidationError):
        AIDerivationSample.model_validate(data)


@pytest.mark.parametrize("collection", ["methods", "assumptions", "steps"])
def test_duplicate_sample_ids_are_rejected(bank, collection):
    data = bank.samples["sample-001"].model_dump(mode="json")
    data[collection].append(copy.deepcopy(data[collection][0]))
    with pytest.raises(ValidationError, match="Duplicate"):
        AIDerivationSample.model_validate(data)


@pytest.mark.parametrize("field,value", [
    ("template_id", "missing"),
    ("claimed_conclusion", {"source": "x.__class__", "latex": "x"}),
    ("claimed_conclusion", {"source": "z+1", "latex": "z+1"}),
])
def test_loader_checks_sample_provenance_and_parser_sources(content_dirs, field, value):
    mutate(content_dirs[1], "sample-001", lambda d: d.update({field: value}))
    with pytest.raises(ChallengeLoadError, match="sample-001"):
        load_dirs(content_dirs)


@pytest.mark.parametrize("edit", [
    lambda d: d.update(template_id="missing"),
    lambda d: d["perturbation"].update(template_id="integral-endpoint"),
    lambda d: d["perturbation"].update(rule_id="missing"),
    lambda d: d["perturbation"].update(condition_id="missing"),
    lambda d: d["perturbation"]["new_value"].update(source="9"),
    lambda d: d["accepted_answers"][0]["answer"].update(step_id="missing"),
    lambda d: d["accepted_answers"][0]["answer"].update(assumption_id="missing"),
    lambda d: d["accepted_answers"][0]["evidence_matches"][0].update(rule_id="missing"),
    lambda d: d["accepted_answers"][0].update(evidence_matches=[{"rule_id": "check-substitute-a", "outcome": "zero_divisor"}]),
    lambda d: d["accepted_answers"].append(copy.deepcopy(d["accepted_answers"][0])),
])
def test_loader_rejects_invalid_mode_a_bindings(content_dirs, edit):
    mutate(content_dirs[0], "practice-001", edit)
    with pytest.raises(ChallengeLoadError, match="practice-001"):
        load_dirs(content_dirs)


def test_mode_a_answers_keep_complete_tuples_and_conjunctive_evidence(bank):
    entries = bank.challenges["practice-002"].accepted_answers
    assert [(entry.answer.step_id, entry.answer.assumption_id, entry.answer.reason_category.value) for entry in entries] == [
        ("change-variable", "regular-upper-bound", "improper_endpoint"),
        ("change-variable", "positive-u", "improper_endpoint"),
    ]
    assert all(len(entry.evidence_matches) == 2 for entry in entries)
    assert entries[0].evidence_matches[1].rule_id != entries[1].evidence_matches[1].rule_id


@pytest.mark.parametrize("id,field", [("practice-003", "template_id"), ("practice-006", "sample_id")])
def test_loader_rejects_other_dangling_references(content_dirs, id, field):
    mutate(content_dirs[0], id, lambda d: d.update({field: "missing"}))
    with pytest.raises(ChallengeLoadError, match=id):
        load_dirs(content_dirs)


def test_reviewed_challenge_cannot_publish_a_draft_sample(content_dirs):
    mutate(content_dirs[1], "sample-001", lambda d: d.update(review={"status": "draft", "reviewer": None, "basis": "Synthetic unpublished sample"}))
    mutate(content_dirs[0], "practice-006", lambda d: d.update(review={"status": "reviewed", "reviewer": "TEST FIXTURE ONLY", "basis": "Synthetic test"}))
    with pytest.raises(ChallengeLoadError, match="unreviewed sample"):
        load_dirs(content_dirs)


@pytest.mark.parametrize("index", [0, 1])
def test_loader_rejects_duplicate_top_level_ids(content_dirs, index):
    directory = content_dirs[index]
    source = sorted(directory.glob("*.json"))[0]
    (directory / "duplicate.json").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(ChallengeLoadError, match="Duplicate content ID"):
        load_dirs(content_dirs)


def test_loader_reports_missing_empty_and_malformed_content(content_dirs, tmp_path):
    with pytest.raises(ChallengeLoadError, match="does not exist"):
        load_challenges(load_templates(), content_dirs[0], tmp_path / "absent")
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ChallengeLoadError, match="no JSON"):
        load_challenges(load_templates(), empty, content_dirs[1])
    (content_dirs[1] / "broken.json").write_text("{", encoding="utf-8")
    with pytest.raises(ChallengeLoadError, match="broken.json"):
        load_dirs(content_dirs)


def test_public_projection_uses_allowlists_and_never_reveals_private_metadata(bank):
    bank = published_fixture(bank)
    before = {id: bank.public_detail(id).model_dump(mode="json") for id in bank.challenges}
    sentinel = "PRIVATE-ANSWER-ANNOTATION"
    for sample in bank.samples.values():
        sample.category = "flawed"
        sample.rubric.mathematical_basis = [sentinel]
        sample.rubric.actual_conclusion.latex = sentinel
        sample.rubric.remediation = sentinel
        sample.problem.well_formedness = WellFormedness.NO_SOLUTION
        sample.problem.computation = None
        for note in sample.annotations:
            note.basis = sentinel
    for content in [*bank.samples.values(), *bank.templates.values()]:
        steps = content.steps if isinstance(content, AIDerivationSample) else content.correct_steps
        for step in steps:
            step.explanation = sentinel
            step.verification = DimensionResult(labels={"Unknown"}, reason_if_unknown=sentinel)
            step.assumption_ids = []
        for method in content.methods:
            method.description = sentinel
        for assumption in content.assumptions:
            assumption.state = "perturbed_false"
    for id in bank.challenges:
        public = bank.public_detail(id).model_dump(mode="json")
        assert public == before[id]
        assert sentinel not in json.dumps(public)
        assert set(public["steps"][0]) == {"id", "number", "input", "output", "method_id", "transformation_kind"}
        assert "well_formedness" not in public["problem"] and "computation" not in public["problem"]
        assert set(public["methods"][0]) == {"id", "name"}
        assert not set(public) & {"category", "rubric", "annotations", "review", "accepted_answers"}
    assert len(bank.public_summaries()) == 10


def test_mode_c_option_structure_does_not_encode_the_answer_category(bank):
    bank = published_fixture(bank)
    public = [bank.public_detail(f"practice-{number:03}") for number in range(6, 11)]
    assert all(item.reason_options == public[0].reason_options for item in public)
    assert all(len(item.assumption_options) == 3 and len(item.steps) == 3 for item in public)
    assert all([option.id for option in item.assumption_options] == ["premise-001", "premise-002", "premise-003"] for item in public)
    assert all(item.title.startswith("Practice ") for item in public)


def test_mode_b_goal_is_required_and_exposed_without_a_verdict(bank):
    bank = published_fixture(bank)
    assert bank.public_detail("practice-003").goal.value == "invalidate_original_derivation"
    assert bank.public_detail("practice-005").goal.value == "change_conclusion"
    data = bank.challenges["practice-003"].model_dump(mode="json")
    del data["goal"]
    with pytest.raises(ValidationError, match="Field required"):
        CONFIG.validate_python(data)


def test_loading_and_presentation_do_not_start_the_engine_or_workers(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Content loading must not compute or grade")
    monkeypatch.setattr("app.engine.classifier.analyze", forbidden)
    monkeypatch.setattr("app.core.isolation.ComputationExecutor.run", forbidden)
    bank = published_fixture(load_challenges(load_templates()))
    assert all(bank.public_detail(id) is not None for id in bank.challenges)
