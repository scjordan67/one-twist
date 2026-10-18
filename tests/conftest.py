import json

import pytest

from app.templates.loader import DEFAULT_DIRECTORY


@pytest.fixture
def template_data():
    return json.loads((DEFAULT_DIRECTORY / "linear-degeneration.json").read_text(encoding="utf-8"))
