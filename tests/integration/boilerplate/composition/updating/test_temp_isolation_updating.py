"""Temp-directory isolation for the updating package.

Seam: the autouse `isolated_temp` fixture in the composition conftest, which
moves temp-directory lookups under a test's `tmp_path` for tests in this
package. Source of truth: the lookups a clone or an update copy reads (`TMP`,
`TEMP`, `TMPDIR` and `tempfile.gettempdir`) and pytest's `tmp_path`. Copier
clones templates and renders an update's old and new copies in temp
directories; left on the real one they leak on Windows.

Breaking change: dropping this package from `ISOLATED_TEMP_PACKAGES` fails
every test below. They run under the real fixture, with nothing stood in.
"""

from pathlib import Path

import pytest

from tests.integration.boilerplate.composition.temp_lookups import (
    LOOKUPS,
    assert_lookup_under,
)


@pytest.mark.parametrize("lookup", LOOKUPS)
def test_temp_lookup_resolves_under_tmp_path(lookup: str, tmp_path: Path) -> None:
    """Resolve each temp lookup under `tmp_path` for an updating test."""
    assert_lookup_under(lookup, tmp_path)
