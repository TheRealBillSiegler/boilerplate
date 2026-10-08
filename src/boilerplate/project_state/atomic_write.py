"""Write a text file so a reader never sees it half written."""
# Spec: docs/design/07-operational-quality.md §Atomic Staged Write Pattern

import contextlib
import os
import tempfile
from pathlib import Path

__all__ = ["write_text_atomically"]


def write_text_atomically(path: Path, text: str) -> None:
    r"""Replace the file at `path` with `text` in one rename.

    The text goes to a temporary file in the same directory, which is then
    renamed over the target, so a crash leaves the old file or the whole new
    one. The file is written as UTF-8 with LF line endings on every platform.

    Args:
        path: The file to create or replace; missing parent directories are
            created.
        text: The full new content.

    Raises:
        OSError: If the temporary file cannot be written or renamed; the
            temporary file is removed and the old file is untouched.

    Examples:
        >>> import tempfile
        >>> with tempfile.TemporaryDirectory() as directory:
        ...     target = Path(directory) / "state.yml"
        ...     write_text_atomically(target, "a: 1\n")
        ...     target.read_text(encoding="utf-8")
        'a: 1\n'
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        dir=path.parent, prefix=f"{path.name}.tmp."
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        Path(temporary).replace(path)
    except BaseException:
        with contextlib.suppress(OSError):
            Path(temporary).unlink()
        raise
