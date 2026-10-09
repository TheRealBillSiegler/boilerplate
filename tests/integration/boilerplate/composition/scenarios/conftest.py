"""Collection hook for the composition scenarios."""

from pathlib import Path

import pytest


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Auto-apply the `scenario` marker to every test under this directory."""
    scenarios_dir = Path(__file__).parent
    for item in items:
        if item.path.is_relative_to(scenarios_dir):
            item.add_marker(pytest.mark.scenario)
