"""Fingerprint a template's source content for the lock."""
# Spec: docs/design/02-data-models.md §Lock File Model

import hashlib
from pathlib import Path
from typing import Final

_EXCLUDED_DIRS: Final = frozenset(
    {
        ".git",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "node_modules",
    }
)
_TEXT_PROBE: Final = 8000
"""How many leading bytes git inspects for a NUL byte to call a file binary."""


def _content_as_git_sees_it(content: bytes) -> bytes:
    """Return `content` with CRLF line endings turned to LF unless it is binary."""
    if b"\0" in content[:_TEXT_PROBE]:
        return content
    return content.replace(b"\r\n", b"\n")


def template_checksum(folder: Path) -> str:
    """Return the SHA-256 of the template source in `folder`, prefixed ``sha256:``.

    The hash covers every file outside git history, bytecode and tool caches,
    sorted by forward-slash path relative to `folder`, each file's path followed
    by its content. Content is compared the way git does, so a checkout that
    turned LF into CRLF has the checksum of one that did not; a file with a NUL
    byte is binary and is hashed as it is.

    Args:
        folder: The template source, such as a release checkout.

    Returns:
        The digest, ``sha256:`` then 64 hex digits.

    Examples:
        >>> import tempfile
        >>> with tempfile.TemporaryDirectory() as directory:
        ...     _ = (Path(directory) / "a.txt").write_text("hi", encoding="utf-8")
        ...     template_checksum(Path(directory))[:14]
        'sha256:5fc5b37'
    """
    files = sorted(
        (path.relative_to(folder).as_posix(), path)
        for path in folder.rglob("*")
        if path.is_file() and _EXCLUDED_DIRS.isdisjoint(path.relative_to(folder).parts)
    )
    digest = hashlib.sha256()
    for relative, path in files:
        digest.update(relative.encode("utf-8"))
        digest.update(_content_as_git_sees_it(path.read_bytes()))
    return f"sha256:{digest.hexdigest()}"
