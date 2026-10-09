"""Temp-directory lookups the composition isolation tests read."""

import os
import tempfile
from collections.abc import Callable
from pathlib import Path

LOOKUPS: dict[str, Callable[[], str]] = {
    "TMP": lambda: os.environ.get("TMP", ""),
    "TEMP": lambda: os.environ.get("TEMP", ""),
    "TMPDIR": lambda: os.environ.get("TMPDIR", ""),
    "tempfile.gettempdir": tempfile.gettempdir,
}
"""The lookups a clone or an update copy reads, keyed by display name."""


def assert_lookup_under(lookup: str, root: Path) -> None:
    """Assert that a temp lookup resolves under `root`.

    Args:
        lookup: A key of `LOOKUPS`.
        root: The directory the lookup must resolve beneath.

    Raises:
        AssertionError: If the lookup returns a path outside `root`.
    """
    found = LOOKUPS[lookup]()
    assert Path(found).is_relative_to(root), f"{lookup} returned {found!r}"
