"""Shared test fixtures."""

import pytest
from pathlib import Path


@pytest.fixture
def flows_dir():
    return Path(__file__).parent.parent.parent / "flows"


