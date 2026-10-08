"""Run an update plan: the staging, the layers, the copy back and what follows."""
# Spec: docs/design/06-project-lifecycle.md §Part 2: Project Update

import logging
from typing import Any

from boilerplate.common.exceptions import UpdateTaskFailedError
from boilerplate.composition.staging import IntentOperation, StagingWorktree
from boilerplate.composition.updating.failed_task import FailedTask
from boilerplate.composition.updating.layer_updater import update_layer
from boilerplate.composition.updating.recorded_answers import (
    read_recorded_answers_by_layer,
)
from boilerplate.composition.updating.step_inputs import StepInputs
from boilerplate.composition.updating.task_failure_choice import TaskFailureChoice
from boilerplate.composition.updating.task_failure_handler import TaskFailureHandler
from boilerplate.composition.updating.task_run import TaskRun
from boilerplate.composition.updating.task_runner import run_update_tasks
from boilerplate.composition.updating.update_options import UpdateOptions
from boilerplate.composition.updating.update_outcome import UpdateOutcome
from boilerplate.composition.updating.update_status import UpdateStatus
from boilerplate.composition.updating.walk.update_lock_writer import write_update_lock
from boilerplate.composition.updating.walk.update_recorder import UpdateRecorder
from boilerplate.composition.updating.walk.walk_inputs import WalkInputs
from boilerplate.integrations.copier_types import TaskError

_logger = logging.getLogger(__name__)


def conflict_message(layer: str, conflicts: tuple[str, ...]) -> str:
    """Say which layer's update left conflicts and in which files.

    Args:
        layer: The layer that paused the walk.
        conflicts: The conflicted paths.

    Returns:
        The message the conflict record and the pause both carry.

    Examples:
        >>> conflict_message("service", ("SERVICE.md", "Dockerfile"))
        "Layer 'service' left merge conflicts in: SERVICE.md, Dockerfile."
    """
    return f"Layer '{layer}' left merge conflicts in: {', '.join(conflicts)}."


class UpdateWalk:
    """One run of an update plan in a staging worktree.

    The layers update in the worktree, ancestors first, with a commit after each
    so Copier will update the next. A layer that leaves conflicts pauses the walk.
    Otherwise the worktree is copied back into the user's checkout, the
    composition's tasks run there once, and the lock and the migration record are
    written. A task that fails after the copy back is handed to the caller's
    handler, which keeps the update or undoes it.
    """

    def __init__(
        self,
        inputs: WalkInputs,
        *,
        on_task_failure: TaskFailureHandler,
        boilerplate_version: str,
    ) -> None:
        """Prepare a run of `inputs`; nothing is staged until ``execute``.

        Args:
            inputs: The project, request, plan and checkouts.
            on_task_failure: Decides what a failed task does to the update.
            boilerplate_version: The version of the tool, recorded in the lock.
        """
        self._inputs = inputs
        self._on_task_failure = on_task_failure
        self._boilerplate_version = boilerplate_version
        self._ran: list[str] = []
        self._secrets: dict[str, Any] = {}

    def execute(self) -> UpdateOutcome:
        """Run the plan.

        Returns:
            What the walk did: updated, paused on a conflict, or undone after a
            failed task.

        Raises:
            UpdateTaskFailedError: If a task failed and the handler kept the
                files; the lock is written and the failure recorded first.
            UpdateCheckoutChangedError: If the checkout changed during the walk.
            RecordedAnswerRejectedError: If a layer's target rejects a recorded
                answer and the step does not prompt.
        """
        plan = self._inputs.plan
        with StagingWorktree(
            self._inputs.project,
            operation=IntentOperation.UPDATE,
            template_ref=plan.root_release.ref,
        ) as staging:
            conflicts = self._update_layers(staging)
            if conflicts:
                return self._pause(staging, conflicts)
            staging.copy_back()
            return self._finish(staging)

    def _update_layers(self, staging: StagingWorktree) -> tuple[str, ...]:
        """Update each layer in the worktree and return the paused layer's conflicts.

        Returns:
            The conflicted paths of the layer that paused the walk; empty when
            every layer merged cleanly.
        """
        request = self._inputs.request
        options = UpdateOptions(
            skip_tasks=True,
            quiet=request.quiet,
            interactive=request.interactive,
            skip_answered=request.skip_answered,
        )
        walk_answers = read_recorded_answers_by_layer(self._inputs.project)
        for step in self._inputs.plan.steps:
            self._secrets.update(
                update_layer(
                    staging.path,
                    step.release,
                    step.views,
                    StepInputs(
                        supplied=request.supplied,
                        secrets=self._secrets,
                        walk_answers=walk_answers,
                    ),
                    options,
                )
            )
            self._ran.append(step.layer)
            conflicts = staging.unmerged_paths()
            if conflicts:
                return conflicts
            staging.commit_layer(f"Update {step.layer} to {step.release.ref}")
        return ()

    def _pause(
        self, staging: StagingWorktree, conflicts: tuple[str, ...]
    ) -> UpdateOutcome:
        """Bring the partial update back and record where to resume from.

        The layers finished so far, the paused layer included, are copied back
        with the paused layer's conflict markers and unmerged index entries. The
        conflict record names every layer's target and the finished layers; no
        lock is written.
        """
        plan = self._inputs.plan
        staging.copy_back(paused=True)
        paused_at = self._ran[-1]
        UpdateRecorder(self._inputs.project, plan.lock).conflict(
            f"{plan.root}@{plan.targets[plan.root]}",
            conflict_message(paused_at, conflicts),
            targets=plan.targets,
            finished=(*plan.skipped, *self._ran),
        )
        return self._outcome(UpdateStatus.PAUSED, paused_at, conflicts)

    def _finish(self, staging: StagingWorktree) -> UpdateOutcome:
        """Run the tasks, then write the lock and the record, or undo the update."""
        failed = self._run_tasks()
        if failed is None:
            return self._complete(staging, None)
        untracked = staging.untracked_in_checkout()
        if self._on_task_failure(failed) is TaskFailureChoice.UNDO:
            staging.undo_copy_back(untracked)
            _logger.warning("Undid the update after a failed task: %s", failed.command)
            return self._outcome(UpdateStatus.UNDONE)
        return self._complete(staging, failed)

    def _run_tasks(self) -> FailedTask | None:
        """Run the composition's tasks once in the user's checkout.

        Returns:
            The task that failed; ``None`` when they all passed or none ran.
        """
        inputs = self._inputs
        if inputs.request.no_tasks or not inputs.plan.tasks:
            return None
        try:
            run_update_tasks(
                inputs.project,
                inputs.plan.root_release,
                inputs.plan.task_view,
                TaskRun(tasks=inputs.plan.tasks, secrets=self._secrets),
                UpdateOptions(quiet=inputs.request.quiet),
            )
        except TaskError as error:
            return FailedTask.from_error(error)
        return None

    def _complete(
        self, staging: StagingWorktree, failed: FailedTask | None
    ) -> UpdateOutcome:
        """Write the lock and the record of an update whose files are kept.

        Raises:
            UpdateTaskFailedError: If `failed` is a task that failed.
        """
        inputs = self._inputs
        lock = write_update_lock(
            inputs.project,
            staging,
            inputs.plan.lock,
            self._boilerplate_version,
            inputs.checkouts,
        )
        recorder = UpdateRecorder(inputs.project, inputs.plan.lock)
        if failed is None:
            recorder.success(lock.root_template)
            return self._outcome(UpdateStatus.UPDATED)
        message = (
            f"Task '{failed.command}' exited with status {failed.returncode} after "
            "the update's files were copied back. The files are kept and "
            "boilerplate.lock is written."
        )
        recorder.failed(lock.root_template, message)
        raise UpdateTaskFailedError(
            message, task=failed.command, remediation=failed.rerun
        )

    def _outcome(
        self,
        status: UpdateStatus,
        paused_at: str | None = None,
        conflicts: tuple[str, ...] = (),
    ) -> UpdateOutcome:
        """Describe what the walk did."""
        return UpdateOutcome(
            status=status,
            updated=tuple(self._ran),
            skipped=self._inputs.plan.skipped,
            paused_at=paused_at,
            conflicts=conflicts,
            warnings=self._inputs.plan.warnings,
        )
