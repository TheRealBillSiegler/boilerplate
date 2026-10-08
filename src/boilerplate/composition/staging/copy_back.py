"""Copy a staging worktree's state back into the user's checkout through git."""

import logging
from pathlib import Path

from boilerplate.common.exceptions import UpdateCheckoutChangedError
from boilerplate.composition.staging.git_commands import run_git

_logger = logging.getLogger(__name__)


def require_checkout_unchanged(project: Path, start_commit: str) -> None:
    """Check the user's checkout is at `start_commit` with no changes.

    Args:
        project: The user's checkout.
        start_commit: The commit the checkout was at when staging began.

    Raises:
        UpdateCheckoutChangedError: If HEAD moved, or the working tree has
            changes, untracked files included; copying back would overwrite
            the user's work.
    """
    head = run_git(project, "rev-parse", "HEAD").strip()
    if head != start_commit:
        raise UpdateCheckoutChangedError(
            "The checkout moved to another commit while the update ran; "
            "nothing was written.",
            remediation="Run 'boilerplate update' again.",
        )
    if run_git(project, "status", "--porcelain").strip():
        raise UpdateCheckoutChangedError(
            "The checkout changed while the update ran; nothing was written.",
            remediation="Commit or stash your changes, then run "
            "'boilerplate update' again.",
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
