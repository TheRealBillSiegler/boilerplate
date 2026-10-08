"""Copy a staging worktree's state back into the user's checkout through git."""

import logging
from collections.abc import Sequence
from pathlib import Path

from boilerplate.common.exceptions import UpdateCheckoutChangedError
from boilerplate.composition.staging.git_commands import run_git
from boilerplate.composition.staging.intent_operation import IntentOperation

_logger = logging.getLogger(__name__)


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
    ``commit``, and the listed files, which the copy back or a task added, are
    deleted along with the folders that leave empty. A file not listed stays: the
    caller lists what it saw, so work the user did since is not touched.

    Args:
        project: The user's checkout.
        commit: The commit the checkout was at when staging began.
        untracked: Paths, relative to the checkout, of the files to delete.

    Raises:
        ValueError: If a listed path escapes the checkout.
    """
    root = project.resolve()
    targets = [(root / relative).resolve() for relative in untracked]
    for relative, target in zip(untracked, targets, strict=True):
        if not target.is_relative_to(root):
            raise ValueError(f"'{relative}' escapes the project.")
    run_git(
        project, "restore", f"--source={commit}", "--worktree", "--staged", "--", ":/"
    )
    for target in targets:
        target.unlink(missing_ok=True)
        for parent in target.parents:
            if parent == root or any(parent.iterdir()):
                break
            parent.rmdir()
    _logger.debug("Undid the update in %s from %s", project, commit)
