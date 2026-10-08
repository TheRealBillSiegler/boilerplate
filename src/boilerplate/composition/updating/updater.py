"""The Application Layer component that walks an update across a project's layers."""
# Spec: docs/design/04-composition-engine.md §Safe Update

import logging
import tempfile
from pathlib import Path

from boilerplate import __version__
from boilerplate.common.exceptions import ActionRequiredError
from boilerplate.composition.staging import check_project_ready
from boilerplate.composition.updating.task_failure_handler import (
    TaskFailureHandler,
    keep_files,
)
from boilerplate.composition.updating.update_outcome import UpdateOutcome
from boilerplate.composition.updating.update_request import UpdateRequest
from boilerplate.composition.updating.update_status import UpdateStatus
from boilerplate.composition.updating.walk.update_walk import (
    UpdateWalk,
    conflict_message,
)
from boilerplate.composition.updating.walk.walk_inputs import WalkInputs
from boilerplate.composition.updating.walk.walk_planner import plan_walk
from boilerplate.project_state.lock_file import read_lock
from boilerplate.repository.release_checkouts import ReleaseCheckouts

_logger = logging.getLogger(__name__)

_PAUSE_REMEDIATION = (
    "Resolve conflicts and commit, then run 'boilerplate update' again. "
    "'git reset' and then 'git stash --include-untracked' set the partial update "
    "aside."
)


class Updater:
    """Updates a composed project to newer releases of its layers.

    The update plans first, with every check that can stop it before any staging
    folder exists. It then updates each layer in a detached worktree of the
    project, ancestors first, committing after each so Copier will update the
    next, and brings the result back into the user's checkout as the uncommitted
    changes plain Copier leaves. The composition's tasks run once after that, and
    the lock and the migration record are written last.
    """

    def __init__(
        self,
        *,
        on_task_failure: TaskFailureHandler = keep_files,
        boilerplate_version: str = __version__,
    ) -> None:
        """Prepare an updater.

        Args:
            on_task_failure: Called with the task that failed after the files
                were copied back; returns whether to keep the update or undo it.
                The default keeps it, as a caller that cannot ask does.
            boilerplate_version: The version of the tool, recorded in the lock.
        """
        self._on_task_failure = on_task_failure
        self._boilerplate_version = boilerplate_version

    def update(
        self, project: Path, request: UpdateRequest | None = None
    ) -> UpdateOutcome:
        """Update `project`'s layers to the targets and write its lock.

        A layer whose update leaves conflicts pauses the walk: the layers
        finished so far and the conflicted files are in the checkout, and this
        raises. Run it again after resolving and committing to finish the update
        to the targets the pause recorded.

        Args:
            project: The project, a clean git repository root with a
                ``boilerplate.lock``.
            request: What the user asked of the update; the defaults move every
                layer to its latest release without prompting.

        Returns:
            What the walk did: updated, or undone after a failed task.

        Raises:
            ActionRequiredError: If a layer's update left conflicts.
            UpdateTaskFailedError: If a task failed and the files were kept.
            UpdateProjectNotReadyError: If the project is dirty or not a
                repository root.
            UpdateSubmodulesUnsupportedError: If the project has submodules.
            UpdateTargetMismatchError: If an explicit target differs from a
                paused update's recorded one.
            UpdateLayerDriftError: If a layer and an ancestor both disagree with
                the lock.
            UpdateDowngradeError: If a target is older than a layer's recorded
                version.
            AnswersFileIncompleteError: If a layer's answers file lacks answers
                its view asks for.
            RecordedAnswerRejectedError: If a layer's target rejects a recorded
                answer and the step does not prompt.
            UpdateCheckoutChangedError: If the checkout changed during the walk.
        """
        outcome = self.run(project, request)
        if outcome.status is UpdateStatus.PAUSED:
            raise ActionRequiredError(
                conflict_message(outcome.paused_at or "", outcome.conflicts),
                remediation=_PAUSE_REMEDIATION,
            )
        return outcome

    def run(self, project: Path, request: UpdateRequest | None = None) -> UpdateOutcome:
        """Run the update and report a pause as an outcome rather than raising it.

        Args:
            project: The project, a clean git repository root with a
                ``boilerplate.lock``.
            request: What the user asked of the update; the defaults move every
                layer to its latest release without prompting.

        Returns:
            What the walk did: updated, paused on a conflict or undone.

        Raises:
            UpdateTaskFailedError: If a task failed and the files were kept.
            UpdateProjectNotReadyError: If the project is dirty or not a
                repository root.
            UpdateSubmodulesUnsupportedError: If the project has submodules.
            UpdateTargetMismatchError: If an explicit target differs from a
                paused update's recorded one.
            UpdateLayerDriftError: If a layer and an ancestor both disagree with
                the lock.
            UpdateDowngradeError: If a target is older than a layer's recorded
                version.
            AnswersFileIncompleteError: If a layer's answers file lacks answers
                its view asks for.
            RecordedAnswerRejectedError: If a layer's target rejects a recorded
                answer and the step does not prompt.
            UpdateCheckoutChangedError: If the checkout changed during the walk.
        """
        request = request or UpdateRequest()
        check_project_ready(project)
        lock = read_lock(project)
        with (
            ReleaseCheckouts() as checkouts,
            tempfile.TemporaryDirectory(
                prefix="boilerplate-views-", ignore_cleanup_errors=True
            ) as workdir,
        ):
            plan = plan_walk(project, request, lock, checkouts, Path(workdir))
            for warning in plan.warnings:
                _logger.warning(warning)
            return UpdateWalk(
                WalkInputs(project, request, plan, checkouts),
                on_task_failure=self._on_task_failure,
                boilerplate_version=self._boilerplate_version,
            ).execute()
