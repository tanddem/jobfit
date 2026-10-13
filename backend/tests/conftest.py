"""Shared paths and loaders for the rubric and the fixture cases."""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "fixtures"


def load_json(path):
    """Read a UTF-8 JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def rubric():
    """The parsed rubric.json from the project root."""
    return load_json(ROOT / "rubric.json")
