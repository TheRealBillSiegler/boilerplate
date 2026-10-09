"""The task that failed in one run, and what the caller chose to do about it."""
# Spec: docs/design/04-composition-engine.md §Safe Update

import logging
from collections.abc import Callable, Collection
from pathlib import Path

from boilerplate.common.exceptions import UpdateTaskFailedError
from boilerplate.composition.staging.ignored_files import (
    list_ignored_paths,
    list_new_ignored_paths,
)
from boilerplate.composition.updating.failed_task import FailedTask
from boilerplate.composition.updating.keep_or_undo import keep_or_undo
from boilerplate.composition.updating.task_failure_handler import TaskFailureHandler
from boilerplate.integrations.copier_types import TaskError

__all__ = ["TaskFailure"]

_logger = logging.getLogger(__name__)


class TaskFailure:
    """Run a run's tasks, and hold the failure the caller chose to keep.

    An update, an add and the reruns that finish them each run their tasks
    once in the user's checkout. A task that fails is handed to the caller's
    handler, which keeps the files or undoes the run; a kept failure is held
    here until the run has recorded itself and can report it.

    Before the tasks run, the ignored entries in the checkout are noted. An undo
    never deletes what git ignores, so after one the entries that are new are
    named: in this attribute, for the run's outcome, and in a warning. A folder
    git ignores is one entry, so a change inside one that already existed, such
    as ``.venv/``, is not seen. A rerun that finishes a run cut off during its
    tasks notes the entries when the rerun starts, so an entry the cut-off run's
    tasks made is not named.

    Attributes:
        failed: The task that failed and whose files were kept; ``None`` when
            the tasks passed, none ran, or the run was undone.
        ignored_left: The ignored files and folders the tasks made and an undo
            left in place; empty unless the run was undone.
    """

    def __init__(self, on_task_failure: TaskFailureHandler) -> None:
        """Prepare to run a run's tasks.

        Args:
            on_task_failure: Decides what a failed task does to the run.
        """
        self._on_task_failure = on_task_failure
        self.failed: FailedTask | None = None
        self.ignored_left: tuple[str, ...] = ()

    def run(
        self, tasks: Callable[[], object], *, project: Path, start_commit: str
    ) -> bool:
        """Run the tasks and hand the one that fails to the caller's handler.

        Args:
            tasks: Runs the run's tasks in the user's checkout; it raises
                ``TaskError`` for the task that failed.
            project: The user's checkout.
            start_commit: The commit the checkout was at when the run began.

        Returns:
            Whether the files are kept: ``False`` when a task failed and the
            handler undid the run.
        """
        ignored_before = list_ignored_paths(project)
        try:
            tasks()
        except TaskError as error:
            failed = FailedTask.from_error(error)
            if not keep_or_undo(project, start_commit, failed, self._on_task_failure):
                self._name_ignored_left(project, ignored_before)
                return False
            self.failed = failed
        return True

    def _name_ignored_left(self, project: Path, before: Collection[str]) -> None:
        """Hold and warn of the ignored entries an undo left that `before` lacked."""
        self.ignored_left = list_new_ignored_paths(project, before)
        if self.ignored_left:
            _logger.warning(
                "The undo left these ignored files and folders in place: %s. "
                "Changes inside an ignored folder that was already there, "
                "such as .venv, are not listed.",
                ", ".join(self.ignored_left),
            )

    def raise_if_failed(self, message: Callable[[FailedTask], str]) -> None:
        """Raise the failure of a task whose files were kept, if one failed.

        Args:
            message: Words the failure for the operation that ran the tasks.

        Raises:
            UpdateTaskFailedError: If a task failed and the handler kept the
                files; the remediation is how to run the task by hand.
        """
        if self.failed is not None:
            raise UpdateTaskFailedError(
                message(self.failed),
                task=self.failed.command,
                remediation=self.failed.rerun,
            )
