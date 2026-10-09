"""Run an add plan: the staging, the copy, the copy back and what follows."""
# Spec: docs/design/06-project-lifecycle.md §Part 2: Project Update

import logging
from collections.abc import Mapping
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
from boilerplate.composition.staging.finish_steps import FinishSteps
from boilerplate.composition.staging.finisher import Finisher
from boilerplate.composition.updating.failed_task import FailedTask
from boilerplate.composition.updating.keep_or_undo import keep_or_undo
from boilerplate.composition.updating.recorded_answers import (
    read_recorded_answers_by_layer,
)
from boilerplate.composition.updating.step_inputs import StepInputs
from boilerplate.composition.updating.task_failure_handler import TaskFailureHandler
from boilerplate.composition.updating.task_run import TaskRun
from boilerplate.composition.updating.update_options import UpdateOptions
from boilerplate.integrations.copier_types import TaskError
from boilerplate.models import RestoreKind, RestoreOperation

_logger = logging.getLogger(__name__)


def record_add(
    recorder: AddRecorder, specifier: str, failed: FailedTask | None
) -> None:
    """Append an add's one record, as the run ended.

    Args:
        recorder: The recorder of the project's log.
        specifier: The added layer, ``name@version``.
        failed: The task that failed and whose files were kept; ``None`` when
            the tasks passed or none ran.
    """
    if failed is None:
        recorder.success(specifier)
    else:
        recorder.failed(specifier, add_failure_message(failed))


def add_failure_message(failed: FailedTask) -> str:
    """Say which task failed after an add and what was kept.

    Args:
        failed: The task that failed.

    Returns:
        The message the error carries.
    """
    return (
        f"Task '{failed.command}' exited with status {failed.returncode} after "
        "the layer was added. The files are kept and boilerplate.lock is written."
    )


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
        self._warnings: tuple[str, ...] = ()
        self._failed: FailedTask | None = None

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
            secrets = copy_layer(
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
            self._warnings = staging.warn_uncarried(plan.layer)
            staging.commit_layer(f"Add {plan.layer} {plan.release.ref}")
            return self._finish(staging, secrets)

    def _finish(
        self, staging: StagingWorktree, secrets: Mapping[str, Any]
    ) -> AddOutcome:
        """Copy back, run the tasks, then write the lock and the record, or undo.

        Args:
            staging: The worktree the layer was copied through.
            secrets: The secret answers the copy ended with, for the tasks.

        Raises:
            UpdateTaskFailedError: If a task failed and the handler kept the
                files.
        """
        plan = self._inputs.plan
        finisher = Finisher.for_staging(
            staging,
            operation=RestoreOperation.ADD,
            kind=RestoreKind.COMPLETE,
            targets={plan.layer: plan.version},
            steps=FinishSteps(
                write_record=self._record,
                write_lock=self._write_lock,
                run_tasks=lambda: self._run_tasks(staging, secrets),
            ),
        )
        finisher.copy_back(staging)
        if not finisher.finish():
            return self._outcome(AddStatus.UNDONE)
        if self._failed is not None:
            raise UpdateTaskFailedError(
                add_failure_message(self._failed),
                task=self._failed.command,
                remediation=self._failed.rerun,
            )
        return self._outcome(AddStatus.ADDED)

    def _run_tasks(self, staging: StagingWorktree, secrets: Mapping[str, Any]) -> bool:
        """Run the layer's own tasks once in the user's checkout.

        A task that fails is handed to the caller's handler, which keeps the
        files or undoes the add.

        Args:
            staging: The worktree the layer was copied through.
            secrets: The secret answers the copy ended with, for the tasks.

        Returns:
            Whether the files are kept.
        """
        failed = self._task_failure(secrets)
        if failed is None:
            return True
        if not keep_or_undo(
            staging.project, staging.start_commit, failed, self._on_task_failure
        ):
            return False
        self._failed = failed
        return True

    def _task_failure(self, secrets: Mapping[str, Any]) -> FailedTask | None:
        """Run the layer's tasks and return the one that failed.

        Args:
            secrets: The secret answers the copy ended with, for the tasks.

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
                TaskRun(tasks=plan.tasks, secrets=secrets),
                UpdateOptions(quiet=self._inputs.request.quiet),
            )
        except TaskError as error:
            return FailedTask.from_error(error)
        return None

    def _write_lock(self) -> None:
        """Write the lock with the new layer last."""
        write_add_lock(
            self._inputs.project,
            self._inputs.plan,
            self._boilerplate_version,
            self._inputs.checkouts,
        )

    def _record(self) -> None:
        """Append the add's record: ``success``, or ``failed`` after a kept task."""
        plan = self._inputs.plan
        record_add(
            AddRecorder(self._inputs.project),
            f"{plan.layer}@{plan.version}",
            self._failed,
        )

    def _outcome(self, status: AddStatus) -> AddOutcome:
        """Describe what the add did."""
        return AddOutcome(
            status=status,
            layer=self._inputs.plan.layer,
            version=self._inputs.plan.version,
            warnings=self._warnings,
        )
