from pathlib import Path

from pydantic import ValidationError

from app.core.parsing import MathSyntaxError, parse_math
from app.models import MathExpression, Template
from app.models.domain import Model

DEFAULT_DIRECTORY = Path(__file__).parent / "data"


class TemplateLoadError(ValueError):
    pass


def validate_expressions(value: object, symbols: set[str]) -> None:
    """Validate arithmetic sources in trusted JSON models without evaluating prose."""
    if isinstance(value, MathExpression):
        if value.source is not None:
            parse_math(value.source, symbols=symbols)
    elif isinstance(value, Model):
        for field in type(value).model_fields:
            validate_expressions(getattr(value, field), symbols)
    elif isinstance(value, list):
        for item in value:
            validate_expressions(item, symbols)


def load_templates(directory: Path = DEFAULT_DIRECTORY) -> dict[str, Template]:
    """Fail at startup on invalid content, duplicate IDs or broken references."""
    if not directory.is_dir():
        raise TemplateLoadError(f"Template directory does not exist: {directory}")
    templates: dict[str, Template] = {}
    for path in sorted(directory.glob("*.json")):
        try:
            template = Template.model_validate_json(path.read_text(encoding="utf-8"))
            problem = template.original_problem
            symbols = set(problem.variables) | {item.name for item in problem.parameters}
            validate_expressions(template, symbols)
        except (ValidationError, MathSyntaxError, OSError) as exc:
            raise TemplateLoadError(f"Invalid template {path.name}: {exc}") from exc
        if template.id in templates:
            raise TemplateLoadError(f"Duplicate template ID: {template.id}")
        templates[template.id] = template
    if not templates:
        raise TemplateLoadError("Template directory contains no JSON templates")
    return templates
