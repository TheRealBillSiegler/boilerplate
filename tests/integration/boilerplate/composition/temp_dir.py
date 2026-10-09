"""Temp-directory redirection shared by the composition tests."""

import contextlib
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from plumbum import local


@contextlib.contextmanager
def temp_dir_inside(root: Path) -> Generator[Path]:
    """Point every temp-directory lookup at a directory under `root`.

    Copier clones templates and renders an update's old and new copies in
    temp directories; git subprocesses read the environment and Python
    caches its own lookup in ``tempfile.tempdir``, so both are redirected.
    Git also checks out with LF endings here, whatever ``core.autocrlf`` the
    machine sets: a clone of a layer would otherwise hand Copier CRLF files
    on Windows, and an update would then see every line as changed.

    Args:
        root: The directory to create the temp directory under.

    Yields:
        The temp directory.
    """
    scratch = root / "tmp"
    scratch.mkdir(parents=True, exist_ok=True)
    lf_checkouts = {
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "core.autocrlf",
        "GIT_CONFIG_VALUE_0": "false",
    }
    # Copier runs git through plumbum, whose environment is a copy taken at
    # import, so the settings go to both it and ``os.environ``.
    with pytest.MonkeyPatch.context() as patch, local.env(**lf_checkouts):
        for name in ("TMP", "TEMP", "TMPDIR"):
            patch.setenv(name, str(scratch))
        for name, value in lf_checkouts.items():
            patch.setenv(name, value)
        patch.setattr(tempfile, "tempdir", str(scratch))
        yield scratch
