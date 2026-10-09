"""Temp-directory isolation stays out of the rendering package.

Seam: the autouse `isolated_temp` fixture in the composition conftest, which
must leave temp-directory lookups alone for tests in this package. Source of
truth: the lookups (`TMP`, `TEMP`, `TMPDIR` and `tempfile.gettempdir`) as the
real environment returned them when this module was collected, before any
fixture ran. The rendering tests share the real temp directory and rely on it.

Breaking change: adding this package to `ISOLATED_TEMP_PACKAGES` fails every
test below. They run under the real fixture, with nothing stood in.
"""

import pytest

from tests.integration.boilerplate.composition.temp_lookups import LOOKUPS

REAL = {name: lookup() for name, lookup in LOOKUPS.items()}


@pytest.mark.parametrize("lookup", LOOKUPS)
def test_temp_lookup_keeps_the_real_temp_directory(lookup: str) -> None:
    """Leave each temp lookup unchanged for a rendering test."""
    assert LOOKUPS[lookup]() == REAL[lookup]
