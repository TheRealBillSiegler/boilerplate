"""Run an add plan: the staging, the copy, the copy back and what follows."""
# Spec: docs/design/06-project-lifecycle.md §Part 2: Project Update

import logging
from typing import Any

from boilerplate.common.exceptions import UpdateTaskFailedError
from boilerplate.composition.adding.add_inputs import AddInputs
from boilerplate.composition.adding.add_lock_writer import write_add_lock
from boilerplate.composition.adding.add_outcome import AddOutcome
from boilerplate.composition.adding.add_recorder import AddRecorder
from boilerplate.composition.adding.add_status import AddStatus
from boilerplate.composition.adding.layer_copier import copy_layer
from boilerplate.composition.adding.task_runner import run_add_tasks
from boilerplate.composition.staging import IntentOperation, StagingWorktree
from boilerplate.composition.updating.failed_task import FailedTask
from boilerplate.composition.updating.recorded_answers import (
    read_recorded_answers_by_layer,
)
from boilerplate.composition.updating.step_inputs import StepInputs
from boilerplate.composition.updating.task_failure_choice import TaskFailureChoice
from boilerplate.composition.updating.task_failure_handler import TaskFailureHandler
from boilerplate.composition.updating.task_run import TaskRun
from boilerplate.composition.updating.update_options import UpdateOptions
from boilerplate.integrations.copier_types import TaskError

_logger = logging.getLogger(__name__)


class AddRun:
    """One run of an add plan in a staging worktree.

    The layer copies into the worktree, which is committed so the copy back can
    restore the checkout from it. The checkout then holds the layer as
    uncommitted changes, the layer's tasks run there once, and the lock and the
    migration record are written. A task that fails after the copy back is handed
    to the caller's handler, which keeps the add or undoes it.
    """

    def __init__(
        self,
        inputs: AddInputs,
        *,
        on_task_failure: TaskFailureHandler,
        boilerplate_version: str,
    ) -> None:
        """Prepare a run of `inputs`; nothing is staged until ``execute``.

        Args:
            inputs: The project, request, plan and checkouts.
            on_task_failure: Decides what a failed task does to the add.
            boilerplate_version: The version of the tool, recorded in the lock.
        """
        self._inputs = inputs
        self._on_task_failure = on_task_failure
        self._boilerplate_version = boilerplate_version
        self._secrets: dict[str, Any] = {}

    def execute(self) -> AddOutcome:
        """Run the plan.

        Returns:
            What the add did: added, or undone after a failed task.

        Raises:
            UpdateTaskFailedError: If a task failed and the handler kept the
                files; the lock is written and the failure recorded first.
            UpdateCheckoutChangedError: If the checkout changed during the add.
        """
        plan = self._inputs.plan
        with StagingWorktree(
            self._inputs.project,
            operation=IntentOperation.ADD,
            template_ref=f"{plan.layer}@{plan.version}",
        ) as staging:
            self._secrets = copy_layer(
                staging.path,
                plan.release,
                plan.view,
                StepInputs(
                    supplied=self._inputs.request.supplied,
                    walk_answers=read_recorded_answers_by_layer(staging.path),
                ),
                UpdateOptions(
                    skip_tasks=True,
                    quiet=self._inputs.request.quiet,
                    interactive=self._inputs.request.interactive,
                ),
            )
            staging.commit_layer(f"Add {plan.layer} {plan.release.ref}")
            staging.copy_back()
            return self._finish(staging)

    def _finish(self, staging: StagingWorktree) -> AddOutcome:
        """Run the tasks, then write the lock and the record, or undo the add."""
        failed = self._run_tasks()
        if failed is None:
            return self._complete(staging, None)
        untracked = staging.untracked_in_checkout()
        if self._on_task_failure(failed) is TaskFailureChoice.UNDO:
            staging.undo_copy_back(untracked)
            _logger.warning("Undid the add after a failed task: %s", failed.command)
            return self._outcome(AddStatus.UNDONE)
        return self._complete(staging, failed)

    def _run_tasks(self) -> FailedTask | None:
        """Run the layer's own tasks once in the user's checkout.

        Returns:
            The task that failed; ``None`` when they all passed or none ran.
        """
        plan = self._inputs.plan
        if self._inputs.request.no_tasks or not plan.tasks:
            return None
        try:
            run_add_tasks(
                self._inputs.project,
                plan.release,
                plan.view,
                TaskRun(tasks=plan.tasks, secrets=self._secrets),
                UpdateOptions(quiet=self._inputs.request.quiet),
            )
        except TaskError as error:
            return FailedTask.from_error(error)
        return None

    def _complete(
        self, staging: StagingWorktree, failed: FailedTask | None
    ) -> AddOutcome:
        """Write the lock and the record of an add whose files are kept.

        Raises:
            UpdateTaskFailedError: If `failed` is a task that failed.
        """
        plan = self._inputs.plan
        write_add_lock(
            self._inputs.project,
            staging,
            plan,
            self._boilerplate_version,
            self._inputs.checkouts,
        )
        recorder = AddRecorder(self._inputs.project)
        specifier = f"{plan.layer}@{plan.version}"
        if failed is None:
            recorder.success(specifier)
            return self._outcome(AddStatus.ADDED)
        message = (
            f"Task '{failed.command}' exited with status {failed.returncode} after "
            "the layer's files were copied back. The files are kept and "
            "boilerplate.lock is written."
        )
        recorder.failed(specifier, message)
        raise UpdateTaskFailedError(
            message, task=failed.command, remediation=failed.rerun
        )

    def _outcome(self, status: AddStatus) -> AddOutcome:
        """Describe what the add did."""
        return AddOutcome(
            status=status,
            layer=self._inputs.plan.layer,
            version=self._inputs.plan.version,
        )
