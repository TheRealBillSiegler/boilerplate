"""Fixtures shared by the composition tests."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.integration.boilerplate.composition.family import Family, build_family
from tests.integration.boilerplate.composition.scenarios.builders import (
    temp_dir_inside,
)


@pytest.fixture(scope="session")
def family(tmp_path_factory: pytest.TempPathFactory) -> Family:
    """Build the made-up template family once per xdist worker.

    Returns:
        Each layer's tagged git repository, its tags and its folder at each tag.
    """
    root: Path = tmp_path_factory.mktemp("family")
    return build_family(root)


ISOLATED_TEMP_PACKAGES = (
    Path(__file__).parent / "scenarios",
    Path(__file__).parent / "updating",
)


@pytest.fixture(autouse=True)
def isolated_temp(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[None]:
    """Redirect temp-directory lookups under `tmp_path` for the update tests.

    Applies to the packages in `ISOLATED_TEMP_PACKAGES` and to no others: the
    rendering tests share the real temp directory and must keep it. Pytest has
    no way to add a fixture to a test after collection, so the fixture is
    automatic and decides by the test's location.

    Yields:
        Nothing; the redirect holds until the test ends.
    """
    if not any(request.path.is_relative_to(p) for p in ISOLATED_TEMP_PACKAGES):
        yield
        return
    with temp_dir_inside(tmp_path):
        yield
