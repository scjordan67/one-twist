import json

import pytest

from app.templates.loader import TemplateLoadError, load_templates


def write_template(directory, data, filename="example.json"):
    (directory / filename).write_text(json.dumps(data), encoding="utf-8")


def test_loads_published_library():
    templates = load_templates()
    assert set(templates) == {"linear-degeneration", "integral-endpoint", "cancelled-factor-domain",
                              "squared-candidates-sign", "inverse-square-domain", "real-log-product",
                              "sine-principal-branch", "cosine-quadrant-sign", "derivative-cusp",
                              "stationary-second-derivative", "lhopital-form",
                              "principal-argument-product", "real-square-to-complex-domain",
                              "vector-angle-zero-norm", "line-intersection-all-coordinates"}
    assert templates["integral-endpoint"].conclusion.source == "log(2)"


def test_duplicate_template_id_is_rejected(tmp_path, template_data):
    write_template(tmp_path, template_data)
    write_template(tmp_path, template_data, "second.json")
    with pytest.raises(TemplateLoadError, match="Duplicate template ID"):
        load_templates(tmp_path)


@pytest.mark.parametrize("collection", [
    "assumptions", "methods", "correct_steps", "allowed_perturbations",
    "verification_rules", "explanation_fragments",
])
def test_duplicate_nested_ids_are_rejected(tmp_path, template_data, collection):
    template_data[collection].append(template_data[collection][0])
    write_template(tmp_path, template_data)
    with pytest.raises(TemplateLoadError, match="Duplicate"):
        load_templates(tmp_path)


def test_duplicate_condition_id_is_rejected(tmp_path, template_data):
    conditions = template_data["original_problem"]["conditions"]
    conditions.append(conditions[0])
    write_template(tmp_path, template_data)
    with pytest.raises(TemplateLoadError, match="Duplicate condition"):
        load_templates(tmp_path)


@pytest.mark.parametrize("location,field", [
    ("correct_steps", "assumption_ids"), ("methods", "assumption_ids"),
    ("assumptions", "condition_ids"),
])
def test_dangling_list_references_are_rejected(tmp_path, template_data, location, field):
    template_data[location][0][field] = ["absent"]
    write_template(tmp_path, template_data)
    with pytest.raises(TemplateLoadError, match="Unknown reference"):
        load_templates(tmp_path)


@pytest.mark.parametrize("location,field", [
    ("correct_steps", "method_id"), ("allowed_perturbations", "condition_id"),
])
def test_dangling_scalar_references_are_rejected(tmp_path, template_data, location, field):
    template_data[location][0][field] = "absent"
    write_template(tmp_path, template_data)
    with pytest.raises(TemplateLoadError, match="Unknown reference"):
        load_templates(tmp_path)


def test_dangling_rule_and_explanation_references_are_rejected(tmp_path, template_data):
    template_data["verification_rules"][0]["refs"][0]["id"] = "absent"
    write_template(tmp_path, template_data)
    with pytest.raises(TemplateLoadError, match="Unknown reference"):
        load_templates(tmp_path)
    template_data["verification_rules"][0]["refs"][0]["id"] = "a-nonzero"
    template_data["explanation_fragments"][0]["evidence_keys"] = ["absent"]
    write_template(tmp_path, template_data)
    with pytest.raises(TemplateLoadError, match="Unknown reference"):
        load_templates(tmp_path)


def test_out_of_order_steps_are_rejected(tmp_path, template_data):
    template_data["correct_steps"][0]["number"] = 2
    write_template(tmp_path, template_data)
    with pytest.raises(TemplateLoadError, match="sequential"):
        load_templates(tmp_path)


def test_parser_is_also_applied_to_content_sources(tmp_path, template_data):
    template_data["conclusion"]["source"] = "x.__class__"
    write_template(tmp_path, template_data)
    with pytest.raises(TemplateLoadError, match="Invalid template"):
        load_templates(tmp_path)


def test_unknown_symbols_in_content_are_rejected(tmp_path, template_data):
    template_data["conclusion"]["source"] = "z+1"
    write_template(tmp_path, template_data)
    with pytest.raises(TemplateLoadError, match="Undeclared symbol"):
        load_templates(tmp_path)


def test_missing_and_empty_directories_are_clear_errors(tmp_path):
    with pytest.raises(TemplateLoadError, match="no JSON templates"):
        load_templates(tmp_path)
    with pytest.raises(TemplateLoadError, match="does not exist"):
        load_templates(tmp_path / "missing")


def test_invalid_json_fails_with_filename(tmp_path):
    (tmp_path / "broken.json").write_text("{", encoding="utf-8")
    with pytest.raises(TemplateLoadError, match="broken.json"):
        load_templates(tmp_path)
