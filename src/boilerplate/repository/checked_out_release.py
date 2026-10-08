"""A layer's template as checked out at one release."""

from pathlib import Path
from typing import NamedTuple

from packaging.version import Version


class CheckedOutRelease(NamedTuple):
    """A template checked out at a release, as Copier reads it.

    Attributes:
        path: The checkout's folder; a temporary clone for a git source.
        commit: ``git describe --tags --always`` of the checkout, the value
            Copier records in ``_commit``; ``None`` for a source that is not a
            git repository.
        version: ``commit`` read as a version the way Copier reads it; ``None``
            for a source that is not a git repository or a commit that reads as
            no version.
    """

    path: Path
    commit: str | None
    version: Version | None
