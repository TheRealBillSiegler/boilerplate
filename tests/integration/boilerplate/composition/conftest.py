"""Fixtures shared by the composition tests."""

from pathlib import Path

import pytest

from tests.integration.boilerplate.composition.family import Family, build_family


@pytest.fixture(scope="session")
def family(tmp_path_factory: pytest.TempPathFactory) -> Family:
    """Build the made-up template family once per xdist worker.

    Returns:
        Each layer's tagged git repository, its tags and its folder at each tag.
    """
    root: Path = tmp_path_factory.mktemp("family")
    return build_family(root)
