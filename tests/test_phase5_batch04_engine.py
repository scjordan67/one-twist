"""Real engine/API checks for batch 04 (17-20): complex numbers and vectors."""
import pytest
import sympy as sp
from fastapi.testclient import TestClient

from app.core.parsing import MathSyntaxError, parse_math
from app.engine.classifier import analyze
from app.main import create_app
from app.models.domain import Perturbation, Template
from app.templates.loader import load_templates


@pytest.fixture(scope="module")
def templates():
    return load_templates()


@pytest.fixture(scope="module")
def client(templates):
    with TestClient(create_app()) as client:
        yield client


def change(template, rule_id, value=None, choice_id=None):
    rule = next(r for r in template.allowed_perturbations if r.id == rule_id)
    new_value = next((v for v in rule.allowed_values if v.source == value), None) if value else None
    return Perturbation(template_id=template.id, rule_id=rule.id, condition_id=rule.condition_id,
                        type=rule.type, new_value=new_value, choice_id=choice_id)


# --- 17: principal argument -------------------------------------------------

def test_17_baseline_and_wrap_through_real_spawn_api(client):
    template = load_templates()["principal-argument-product"]
    body = change(template, "change-p", "-1").model_dump(mode="json")
    response = client.post("/api/analyze", json={"template_id": template.id, "perturbation": body})
    assert response.status_code == 200
    data = response.json()
    assert data["execution"]["status"] == "success"
    report = data["report"]
    assert report["first_invalid_step_id"] == "add-principal-arguments"
    assert set(report["method"]["labels"]) == {"Invalid Step"}
    assert set(report["conclusion"]["labels"]) == {"Valid", "Changed Conclusion"}
    assert report["perturbed_outcome"]["value"]["latex"] == sp.latex(-sp.pi / 2)


def test_17_zero_input_is_undefined_not_unknown(templates):
    data = templates["principal-argument-product"].model_dump()
    data["original_problem"]["parameters"][0]["value"] = {"source": "0", "latex": "0"}
    data["original_problem"]["conditions"][0]["predicate"]["right"] = {"source": "0", "latex": "0"}
    report = analyze(Template.model_validate(data)).report
    assert report.perturbed_outcome.status == "undefined"
    assert report.problem_well_formedness.value == "Undefined"


def test_17_negative_real_axis_endpoint_is_pi_not_negative_pi():
    assert sp.arg(-1) == sp.pi
    assert sp.arg(-1) != -sp.pi


# --- 18: complex equation domain -------------------------------------------

def test_18_complex_roots_through_real_spawn_api(client):
    template = load_templates()["real-square-to-complex-domain"]
    body = change(template, "widen-to-complex", choice_id="all-complex").model_dump(mode="json")
    response = client.post("/api/analyze", json={"template_id": template.id, "perturbation": body})
    assert response.status_code == 200
    data = response.json()
    assert data["execution"]["status"] == "success"
    report = data["report"]
    assert report["first_invalid_step_id"] == "real-square-nonnegative"
    assert report["perturbed_outcome"]["status"] == "solution_set"
    assert report["perturbed_outcome"]["completeness"] == "complete"


def test_18_ordering_predicate_on_complex_domain_is_rejected(templates):
    data = templates["real-square-to-complex-domain"].model_dump()
    choice = next(c for r in data["allowed_perturbations"] for c in r["domain_choices"] if c["id"] == "all-complex")
    choice["domain"]["constraints"] = [{"left": {"source": "z", "latex": "z"}, "relation": "ge", "right": {"source": "0", "latex": "0"}}]
    with pytest.raises(Exception, match="ordering"):
        Template.model_validate(data)


def test_18_non_polynomial_complex_equation_is_unknown(templates):
    data = templates["real-square-to-complex-domain"].model_dump()
    data["original_problem"]["computation"]["left"] = {"source": "1/z", "latex": "1/z"}
    data["original_problem"]["conditions"][0]["domain_binding"]["current"]["number_system"] = "complex"
    data["original_problem"]["variables"]["z"] = "complex"
    template = Template.model_validate(data)
    report = analyze(template).report
    assert report.perturbed_outcome.status == "unknown"


# --- 19: vector angle --------------------------------------------------------

def test_19_zero_vector_through_real_spawn_api(client):
    template = load_templates()["vector-angle-zero-norm"]
    body = change(template, "zero-vector", "0").model_dump(mode="json")
    response = client.post("/api/analyze", json={"template_id": template.id, "perturbation": body})
    assert response.status_code == 200
    data = response.json()
    assert data["execution"]["status"] == "success"
    report = data["report"]
    assert report["first_invalid_step_id"] == "normalize-vector-dot"
    assert report["perturbed_outcome"]["status"] == "undefined"
    assert report["problem_well_formedness"] == "WellFormed"


def test_19_dimension_mismatch_is_rejected():
    from app.models.domain import VectorAngleSpec
    with pytest.raises(Exception, match="dimension"):
        VectorAngleSpec(
            u=({"source": "1", "latex": "1"}, {"source": "0", "latex": "0"}),
            v=({"source": "1", "latex": "1"}, {"source": "0", "latex": "0"}, {"source": "0", "latex": "0"}),
        )


# --- 20: 3D line intersection -----------------------------------------------

def test_20_skew_through_real_spawn_api(client):
    template = load_templates()["line-intersection-all-coordinates"]
    body = change(template, "offset-c", "1").model_dump(mode="json")
    response = client.post("/api/analyze", json={"template_id": template.id, "perturbation": body})
    assert response.status_code == 200
    data = response.json()
    assert data["execution"]["status"] == "success"
    report = data["report"]
    assert report["first_invalid_step_id"] == "claim-common-point"
    assert report["perturbed_outcome"]["line_relation"]["relation"] == "skew"
    assert report["perturbed_outcome"]["line_relation"]["intersection_point"] is None
    assert report["comparison"]["changed"] is True


def test_20_reparameterization_control_is_unchanged(templates):
    template = templates["line-intersection-all-coordinates"]
    report = analyze(template, change(template, "scale-b", "2")).report
    assert report.method.labels == {"Valid"}  # type: ignore[comparison-overlap]
    assert report.comparison.changed is False
    assert report.perturbed_outcome.line_relation.relation.value == "intersecting"


def test_20_only_two_of_three_components_matching_is_not_misreported(templates):
    """The 'claim-common-point' checker must catch a candidate that only
    solves x/y but fails z — the exact bug this template exists to catch."""
    template = templates["line-intersection-all-coordinates"]
    report = analyze(template, change(template, "offset-c", "1")).report
    assert report.step["claim-common-point"].labels == {"Invalid Step"}
    assert "residual" in report.step["claim-common-point"].evidence[0].summary


def test_20_zero_direction_is_undefined_not_a_line(templates):
    data = templates["line-intersection-all-coordinates"].model_dump()
    data["original_problem"]["computation"]["second"]["direction"] = [
        {"source": "0", "latex": "0"}, {"source": "0", "latex": "0"}, {"source": "0", "latex": "0"},
    ]
    report = analyze(Template.model_validate(data)).report
    assert report.perturbed_outcome.status == "unknown"


def test_20_parallel_distinct_and_coincident_classification():
    from app.engine.complex_vector import line_intersection_facts
    from app.engine.context import Context
    from app.models.domain import Line3D, LineIntersection3DSpec, Problem

    def make(second_origin):
        expr = lambda s: {"source": s, "latex": s}
        problem = Problem(statement="t", expression=expr("0"), goal="t", variables={}, parameters=[], conditions=[],
                          computation=LineIntersection3DSpec(
                              first=Line3D(origin=(expr("0"), expr("0"), expr("0")), direction=(expr("1"), expr("0"), expr("0"))),
                              second=Line3D(origin=second_origin, direction=(expr("2"), expr("0"), expr("0"))),
                          ))
        return line_intersection_facts(Context(problem), problem.computation)

    parallel = make((({"source": "0", "latex": "0"}), {"source": "1", "latex": "1"}, {"source": "0", "latex": "0"}))
    assert parallel.relation == "parallel_distinct"
    coincident = make((({"source": "1", "latex": "1"}), {"source": "0", "latex": "0"}, {"source": "0", "latex": "0"}))
    assert coincident.relation == "coincident"


# --- malicious / adversarial source strings are rejected by the parser -----

@pytest.mark.parametrize("source", ["__import__('os').system('x')", "1).__class__.__bases__[0]", "open('f')"])
def test_adversarial_component_sources_are_rejected_at_parse_time(source):
    with pytest.raises(MathSyntaxError):
        parse_math(source)


def test_malicious_vector_component_is_rejected_at_load_time(tmp_path, templates):
    import json
    data = templates["vector-angle-zero-norm"].model_dump()
    u = data["original_problem"]["computation"]["u"]
    data["original_problem"]["computation"]["u"] = ({"source": "__import__('os')", "latex": "0"}, u[1])
    (tmp_path / "bad.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(Exception):
        load_templates(tmp_path)
