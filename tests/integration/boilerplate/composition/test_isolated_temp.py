"""Temp-directory isolation for the composition tests.

Seam: the autouse `isolated_temp` fixture in the composition conftest, which
decides by a test's location whether temp-directory lookups move under its
`tmp_path`. Source of truth: the lookups a clone or an update copy reads
(`TMP`, `TEMP`, `TMPDIR` and `tempfile.gettempdir`), and the rule that only
the scenarios and updating packages are redirected while rendering keeps the
real temp directory. Copier clones templates and renders an update's old and
new copies in temp directories; left on the real one they leak on Windows.

Breaking changes: dropping a package from `ISOLATED_TEMP_PACKAGES`, or adding
rendering to it, fails the matching test below.

The fixture is called on a stand-in request placed in each package, because
a test in this module sits outside both packages and the fixture would not
apply to it.
"""

import contextlib
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from tests.integration.boilerplate.composition.conftest import isolated_temp

COMPOSITION = Path(__file__).parent

LOOKUPS: dict[str, Callable[[], str]] = {
    "TMP": lambda: os.environ.get("TMP", ""),
    "TEMP": lambda: os.environ.get("TEMP", ""),
    "TMPDIR": lambda: os.environ.get("TMPDIR", ""),
    "tempfile.gettempdir": tempfile.gettempdir,
}


class _RequestAt:
    """Stand in for the part of a pytest request the fixture reads.

    Attributes:
        path: The path of the test the request is for.
    """

    def __init__(self, path: Path) -> None:
        """Place the request at `path`."""
        self.path = path


def lookup_under_fixture(package: str, lookup: str, tmp_path: Path) -> str:
    """Read a temp lookup while the fixture is active for a test in `package`.

    Args:
        package: The composition subpackage the stand-in test sits in.
        lookup: A key of `LOOKUPS`.
        tmp_path: The `tmp_path` the stand-in test would have.

    Returns:
        What the lookup returned inside the fixture.
    """
    request = cast(
        "pytest.FixtureRequest", _RequestAt(COMPOSITION / package / "test_probe.py")
    )
    fixture = contextlib.contextmanager(isolated_temp.__wrapped__)
    with fixture(request, tmp_path):
        return LOOKUPS[lookup]()


@pytest.mark.parametrize("lookup", LOOKUPS)
@pytest.mark.parametrize("package", ["scenarios", "updating"])
def test_temp_lookup_resolves_under_tmp_path(
    package: str, lookup: str, tmp_path: Path
) -> None:
    """Resolve each temp lookup under `tmp_path` for a test in `package`."""
    assert Path(lookup_under_fixture(package, lookup, tmp_path)).is_relative_to(
        tmp_path
    )


@pytest.mark.parametrize("lookup", LOOKUPS)
def test_rendering_keeps_the_real_temp_directory(lookup: str, tmp_path: Path) -> None:
    """Leave each temp lookup unchanged for a test in the rendering package."""
    assert lookup_under_fixture("rendering", lookup, tmp_path) == LOOKUPS[lookup]()
