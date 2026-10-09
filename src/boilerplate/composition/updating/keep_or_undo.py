"""Keep the files of a run whose task failed, or undo the run, as the caller decides."""
# Spec: docs/design/04-composition-engine.md §Safe Update

import logging
from pathlib import Path

from boilerplate.composition.staging.copy_back import (
    list_untracked_paths,
    undo_working_tree,
)
from boilerplate.composition.updating.failed_task import FailedTask
from boilerplate.composition.updating.task_failure_choice import TaskFailureChoice
from boilerplate.composition.updating.task_failure_handler import TaskFailureHandler

__all__ = ["keep_or_undo"]

_logger = logging.getLogger(__name__)


def keep_or_undo(
    project: Path,
    start_commit: str,
    failed: FailedTask,
    on_task_failure: TaskFailureHandler,
) -> bool:
    """Hand a failed task to the caller's handler and undo the run if it says so.

    The checkout was clean at `start_commit` when the run began, so every
    untracked file in it now is one the copy back or a task wrote. They are
    listed before the handler is asked, so a file the user makes while a prompt
    waits is never removed. An undo restores the tracked files, the lock and
    the migration log among them, from `start_commit`.

    Args:
        project: The user's checkout.
        start_commit: The commit the checkout was at when the run began.
        failed: The task that failed.
        on_task_failure: Decides whether to keep the files or undo.

    Returns:
        Whether the files are kept.
    """
    untracked = list_untracked_paths(project)
    if on_task_failure(failed) is TaskFailureChoice.UNDO:
        undo_working_tree(project, start_commit, untracked)
        _logger.warning("Undid the run after a failed task: %s", failed.command)
        return False
    return True
