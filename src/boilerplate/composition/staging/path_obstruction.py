"""Find the paths a copy back would clobber: ignored files and directories."""

import logging
import posixpath
from collections.abc import Iterable
from pathlib import Path

from boilerplate.common.exceptions import UpdatePathObstructedError
from boilerplate.composition.staging.git_commands import run_git
from boilerplate.composition.staging.working_tree_changes import (
    parse_changed_paths,
)

_logger = logging.getLogger(__name__)


def list_added_paths(
    project: Path, start_commit: str, last_commit: str
) -> tuple[str, ...]:
    """List the paths the walk's commits added to the starting tree.

    Args:
        project: The user's checkout; the worktree shares its object store.
        start_commit: The commit the checkout was at when staging began.
        last_commit: The worktree's newest layer commit.

    Returns:
        The added paths relative to the checkout, in git's order.
    """
    listing = run_git(
        project,
        "diff-tree",
        "-r",
        "--diff-filter=A",
        "--name-only",
        "-z",
        start_commit,
        last_commit,
    )
    return tuple(path for path in listing.split("\0") if path)


def list_uncommitted_paths(worktree: Path) -> tuple[str, ...]:
    """List the paths a worktree reports as changed and not yet committed.

    These are the paths the paused layer's update touched; the caller keeps the
    ones the checkout does not track.

    Args:
        worktree: The staging worktree, whose status is read.

    Returns:
        The changed paths relative to the worktree, untracked files included.
    """
    status = run_git(
        worktree,
        "status",
        "--porcelain=v1",
        "-z",
        "--no-renames",
        "--untracked-files=all",
    )
    return parse_changed_paths(status)


def require_paths_unobstructed(project: Path, candidates: Iterable[str]) -> None:
    """Check that none of the `candidates` already exists untracked in the checkout.

    The checkout is at the starting commit with no changes, so a path that
    exists and is not tracked there is a file or directory git ignores. The
    restore that copies back would overwrite such a file or delete such a
    directory without a word. A directory that holds tracked files is not
    obstructed: the walk replaces those. A directory on the candidate's path
    that is an untracked file obstructs it too.

    Args:
        project: The user's checkout.
        candidates: Paths, relative to the checkout, the copy back will write.

    Raises:
        UpdatePathObstructedError: If any candidate is obstructed; the error
            names every such path and nothing has been written.
    """
    wanted = tuple(dict.fromkeys(candidates))
    if not wanted:
        return
    listing = run_git(project, "ls-files", "-z")
    tracked = frozenset(path for path in listing.split("\0") if path)
    tracked_dirs = frozenset(parent for path in tracked for parent in _parents(path))
    obstructed = tuple(
        path
        for path in wanted
        if path not in tracked and _is_obstructed(project, path, tracked, tracked_dirs)
    )
    if not obstructed:
        return
    _logger.debug("Copy back obstructed by %s", ", ".join(obstructed))
    raise UpdatePathObstructedError(
        "The update cannot be copied back: these paths already exist in your "
        "checkout as files or directories git ignores, and copying back would "
        f"overwrite or delete them: {', '.join(obstructed)}. Nothing was written.",
        paths=obstructed,
        remediation="Move or delete them, then run the command again.",
    )


def _parents(path: str) -> list[str]:
    """Return the directories above `path`, nearest first."""
    parents: list[str] = []
    parent = posixpath.dirname(path)
    while parent:
        parents.append(parent)
        parent = posixpath.dirname(parent)
    return parents


def _is_obstructed(
    project: Path, path: str, tracked: frozenset[str], tracked_dirs: frozenset[str]
) -> bool:
    """Check whether `path`, or a directory above it, is an untracked blocker.

    Nothing resolves through symlinks: a link occupies its own name.
    """
    if _lexists(project, path) and path not in tracked_dirs:
        return True
    return any(
        parent not in tracked
        and parent not in tracked_dirs
        and _lexists(project, parent)
        and (not (project / parent).is_dir() or (project / parent).is_symlink())
        for parent in _parents(path)
    )


def _lexists(project: Path, relative: str) -> bool:
    """Check that `relative` exists in the checkout, a dangling symlink included."""
    return (project / relative).is_symlink() or (project / relative).exists()
