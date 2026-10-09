"""Remove a staging folder and the worktree registration inside it."""

import logging
import shutil
import stat
from collections.abc import Callable
from pathlib import Path

from boilerplate.composition.staging.git_commands import run_git
from boilerplate.integrations.copier_types import ProcessExecutionError

_logger = logging.getLogger(__name__)


def remove_staging_folder(project: Path, folder: Path, worktree: Path) -> None:
    """Remove a staging worktree, then its folder.

    Removal is best effort at every step: it runs on the way out of a failure,
    where a second error would hide the first. The registration is dropped with
    ``git worktree remove --force`` and ``git worktree prune`` run in
    `project`; the folder, the journal beside the worktree included, is then
    deleted.

    Args:
        project: The project the worktree belongs to; may no longer exist.
        folder: The uniquely named staging folder.
        worktree: The worktree inside `folder`.
    """
    if project.is_dir():
        for command in (
            ("worktree", "remove", "--force", str(worktree)),
            ("worktree", "prune"),
        ):
            try:
                run_git(project, *command)
            except ProcessExecutionError:
                _logger.warning("git %s failed for %s", command[1], worktree)
    shutil.rmtree(folder, onexc=_make_writable_and_retry)
    if folder.exists():
        _logger.warning("Staging folder %s could not be removed.", folder)


def _make_writable_and_retry(
    function: Callable[[str], object], path: str, error: BaseException
) -> None:
    """Clear a read-only flag git sets on object files, then retry the removal."""
    if not isinstance(error, PermissionError):
        _logger.warning("Could not remove %s: %s", path, error)
        return
    Path(path).chmod(stat.S_IWRITE)
    try:
        function(path)
    except OSError as retry_error:
        _logger.warning("Could not remove %s: %s", path, retry_error)
