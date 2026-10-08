"""Fixtures for the add integration tests: temp directories stay under pytest's."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.integration.boilerplate.composition.temp_dir import temp_dir_inside


@pytest.fixture(autouse=True)
def isolated_temp(tmp_path: Path) -> Iterator[Path]:
    """Redirect temp-directory lookups under the test's `tmp_path`."""
    with temp_dir_inside(tmp_path) as scratch:
        yield scratch
