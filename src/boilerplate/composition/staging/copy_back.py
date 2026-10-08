"""Copy a staging worktree's state back into the user's checkout through git."""

import logging
from collections.abc import Sequence
from pathlib import Path, PurePosixPath, PureWindowsPath

from boilerplate.common.exceptions import UpdateCheckoutChangedError
from boilerplate.composition.staging.git_commands import run_git
from boilerplate.composition.staging.intent_operation import IntentOperation

_logger = logging.getLogger(__name__)

# Paths per ``git clean`` call, so a long list stays under the command-line limit.
_CLEAN_BATCH = 100


def require_checkout_unchanged(
    project: Path, start_commit: str, operation: IntentOperation
) -> None:
    """Check the user's checkout is at `start_commit` with no changes.

    Args:
        project: The user's checkout.
        start_commit: The commit the checkout was at when staging began.
        operation: The operation whose copy back asks, which the message and
            the remediation name.

    Raises:
        UpdateCheckoutChangedError: If HEAD moved, or the working tree has
            changes, untracked files included; copying back would overwrite
            the user's work.
    """
    head = run_git(project, "rev-parse", "HEAD").strip()
    if head != start_commit:
        raise UpdateCheckoutChangedError(
            "The checkout moved to another commit while the "
            f"{operation.value} ran; nothing was written.",
            remediation=f"Run 'boilerplate {operation.value}' again.",
        )
    if run_git(project, "status", "--porcelain").strip():
        raise UpdateCheckoutChangedError(
            f"The checkout changed while the {operation.value} ran; "
            "nothing was written.",
            remediation="Commit or stash your changes, then run "
            f"'boilerplate {operation.value}' again.",
        )


def restore_working_tree(project: Path, commit: str) -> None:
    """Make the checkout's working tree match `commit`, leaving HEAD and the index.

    ``git restore --source=<commit> --worktree -- :/`` writes the files the
    commit has and removes the tracked files it lacks, so a file the walk added
    and a file it deleted both apply; a copy of the worktree's files cannot
    carry a deletion. The changes stay uncommitted and unstaged.

    Args:
        project: The user's checkout.
        commit: The commit to restore from.
    """
    run_git(project, "restore", f"--source={commit}", "--worktree", "--", ":/")
    _logger.debug("Restored %s from %s", project, commit)


def list_untracked_paths(project: Path) -> tuple[str, ...]:
    """List the files in the checkout git does not track and does not ignore.

    Args:
        project: The user's checkout.

    Returns:
        The paths relative to the checkout, in git's order.
    """
    listing = run_git(project, "ls-files", "--others", "--exclude-standard", "-z")
    return tuple(path for path in listing.split("\0") if path)


def undo_working_tree(project: Path, commit: str, untracked: Sequence[str]) -> None:
    """Return the checkout to `commit`'s files and remove `untracked`.

    Tracked files, in the working tree and the index, are restored from
    ``commit``. The listed files, which the copy back or a task added, are
    removed by ``git clean -f -d`` run from the project root, one literal
    pathspec each, so git decides what a path is: a symlink is removed as
    itself and never followed, and a nested repository that ``ls-files``
    lists as ``dir/`` is skipped rather than unlinked. The folders that leave
    empty go too. A file not listed stays: the caller lists what it saw, so
    work the user did since is not touched.

    Args:
        project: The user's checkout.
        commit: The commit the checkout was at when staging began.
        untracked: Paths, relative to the checkout, of the files to delete.

    Raises:
        ValueError: If a listed path is absolute or leaves the checkout.
    """
    for relative in untracked:
        if _escapes(relative):
            raise ValueError(f"'{relative}' escapes the project.")
    run_git(
        project, "restore", f"--source={commit}", "--worktree", "--staged", "--", ":/"
    )
    for start in range(0, len(untracked), _CLEAN_BATCH):
        batch = untracked[start : start + _CLEAN_BATCH]
        run_git(
            project, "clean", "-f", "-d", "--", *(f":(literal){path}" for path in batch)
        )
    for relative in untracked:
        _remove_emptied_folders(project, relative)
    _logger.debug("Undid the update in %s from %s", project, commit)


def _escapes(relative: str) -> bool:
    """Check whether `relative` is absolute or climbs out of the checkout, by name."""
    path = PurePosixPath(relative.replace("\\", "/"))
    return (
        path.is_absolute()
        or ".." in path.parts
        or bool(PureWindowsPath(relative).drive)
    )


def _remove_emptied_folders(project: Path, relative: str) -> None:
    """Remove the folders above `relative` that the clean left empty.

    The walk goes up by name, never through a symlink, and stops at the first
    folder that is missing, not empty or not a plain directory.
    """
    for parent in PurePosixPath(relative.rstrip("/")).parents:
        if not parent.parts:
            return
        folder = project / parent
        if folder.is_symlink():
            return
        try:
            folder.rmdir()
        except OSError:
            return
