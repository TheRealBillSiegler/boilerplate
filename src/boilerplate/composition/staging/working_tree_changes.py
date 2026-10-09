"""Carry a worktree's uncommitted changes into the user's checkout."""

import logging
import shutil
from pathlib import Path

from boilerplate.composition.staging.git_commands import run_git

_logger = logging.getLogger(__name__)

# The two status characters and the space before the path.
_STATUS_PREFIX_WIDTH = 3


def parse_changed_paths(porcelain_z: str) -> tuple[str, ...]:
    """Read the paths out of ``git status --porcelain=v1 -z --no-renames``.

    Args:
        porcelain_z: The NUL-separated status output; each record is two
            status characters, a space and the path.

    Returns:
        The changed paths in output order, unmerged and untracked ones included.
    """
    return tuple(
        record[_STATUS_PREFIX_WIDTH:] for record in porcelain_z.split("\0") if record
    )


def apply_working_tree_changes(worktree: Path, project: Path) -> None:
    """Make each path the worktree reports as changed match it in the checkout.

    A file the worktree has, with Copier's conflict markers in it where the
    update conflicted, is written to the checkout; a path the worktree lacks is
    removed from the checkout. A symlink is copied as a symlink, unless it
    points outside the worktree. The changes stay unstaged.

    Args:
        worktree: The staging worktree, whose uncommitted state is read.
        project: The user's checkout, written to.

    Raises:
        ValueError: If git reports a path whose directory escapes the project,
            or a symlink that points outside the worktree.
    """
    status = run_git(
        worktree,
        "status",
        "--porcelain=v1",
        "-z",
        "--no-renames",
        "--untracked-files=all",
    )
    root = project.resolve()
    staging_root = worktree.resolve()
    for relative in parse_changed_paths(status):
        # Resolve the parent only: the final name may be a link, and the link
        # itself is what gets written, not whatever it points at.
        joined = root / relative
        parent = joined.parent.resolve()
        if not parent.is_relative_to(root):
            raise ValueError(f"'{relative}' escapes the project.")
        target = parent / joined.name
        source = worktree / relative
        if source.is_symlink() and not source.resolve().is_relative_to(staging_root):
            raise ValueError(
                f"'{relative}' is a symlink that points outside the staging directory."
            )
        if source.is_symlink() or source.is_file():
            parent.mkdir(parents=True, exist_ok=True)
            if target.is_symlink():
                # Writing through the existing link would change what it points at.
                target.unlink()
            shutil.copy2(source, target, follow_symlinks=False)
        else:
            target.unlink(missing_ok=True)
        _logger.debug("Applied the worktree's change to %s", relative)
