"""Fixtures for the composition scenarios: every temp directory stays under pytest's."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.integration.boilerplate.composition.scenarios.builders import (
    extensions_on_path,
    temp_dir_inside,
)


@pytest.fixture(autouse=True)
def isolated_temp(tmp_path: Path) -> Iterator[Path]:
    """Redirect temp-directory lookups under the test's `tmp_path`."""
    with temp_dir_inside(tmp_path) as scratch:
        yield scratch


@pytest.fixture()
def probe_extensions() -> Iterator[None]:
    """Make the probe-only extension modules importable for the test."""
    with extensions_on_path():
        yield


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Auto-apply the `scenario` marker to every test under this directory."""
    scenarios_dir = Path(__file__).parent
    for item in items:
        if item.path.is_relative_to(scenarios_dir):
            item.add_marker(pytest.mark.scenario)
