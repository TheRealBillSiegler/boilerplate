"""The Application Layer component that walks an update across a project's layers."""
# Spec: docs/design/04-composition-engine.md §Safe Update

import logging
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from boilerplate import __version__
from boilerplate.common.exceptions import ActionRequiredError
from boilerplate.composition.staging import (
    IntentOperation,
    StagingWorktree,
    check_project_ready,
)
from boilerplate.composition.updating.layer_updater import update_layer
from boilerplate.composition.updating.step_inputs import StepInputs
from boilerplate.composition.updating.update_options import UpdateOptions
from boilerplate.composition.updating.update_outcome import UpdateOutcome
from boilerplate.composition.updating.update_request import UpdateRequest
from boilerplate.composition.updating.update_status import UpdateStatus
from boilerplate.composition.updating.walk.update_lock_writer import write_update_lock
from boilerplate.composition.updating.walk.update_recorder import UpdateRecorder
from boilerplate.composition.updating.walk.walk_plan import WalkPlan
from boilerplate.composition.updating.walk.walk_planner import plan_walk
from boilerplate.project_state.lock_file import read_lock
from boilerplate.repository.release_checkouts import ReleaseCheckouts

_logger = logging.getLogger(__name__)

_PAUSE_REMEDIATION = (
    "Resolve conflicts and commit, then run 'boilerplate update' again. "
    "'git reset' and then 'git stash --include-untracked' set the partial update "
    "aside."
)


def _conflict_message(layer: str, conflicts: Sequence[str]) -> str:
    """Say which layer's update left conflicts and in which files."""
    return f"Layer '{layer}' left merge conflicts in: {', '.join(conflicts)}."


class Updater:
    """Updates a composed project to newer releases of its layers.

    The walk plans first, with every check that can stop an update before any
    staging folder exists. It then updates each layer in a detached worktree of
    the project, ancestors first, committing after each so Copier will update
    the next, and brings the result back into the user's checkout as the
    uncommitted changes plain Copier leaves. The lock and the migration record
    are written last.
    """

    def __init__(self, *, boilerplate_version: str = __version__) -> None:
        """Prepare an updater.

        Args:
            boilerplate_version: The version of the tool, recorded in the lock.
        """
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
            What the walk did.

        Raises:
            ActionRequiredError: If a layer's update left conflicts.
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
                _conflict_message(outcome.paused_at or "", outcome.conflicts),
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
            What the walk did.

        Raises:
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
            return self._walk(project, request, plan, checkouts)

    def _walk(
        self,
        project: Path,
        request: UpdateRequest,
        plan: WalkPlan,
        checkouts: ReleaseCheckouts,
    ) -> UpdateOutcome:
        """Run the plan's steps in a staging worktree and finish the update."""
        options = UpdateOptions(
            skip_tasks=True,
            quiet=request.quiet,
            interactive=request.interactive,
            skip_answered=request.skip_answered,
        )
        secrets: dict[str, Any] = {}
        ran: list[str] = []
        with StagingWorktree(
            project,
            operation=IntentOperation.UPDATE,
            template_ref=plan.root_release.ref,
        ) as staging:
            for step in plan.steps:
                secrets.update(
                    update_layer(
                        staging.path,
                        step.release,
                        step.views,
                        StepInputs(supplied=request.supplied, secrets=secrets),
                        options,
                    )
                )
                ran.append(step.layer)
                conflicts = staging.unmerged_paths()
                if conflicts:
                    return self._pause(project, staging, plan, tuple(ran), conflicts)
                staging.commit_layer(f"Update {step.layer} to {step.release.ref}")
            staging.copy_back()
            lock = write_update_lock(
                project, staging, plan.lock, self._boilerplate_version, checkouts
            )
        UpdateRecorder(project, plan.lock).success(lock.root_template)
        return UpdateOutcome(
            status=UpdateStatus.UPDATED,
            updated=tuple(ran),
            skipped=plan.skipped,
            warnings=plan.warnings,
        )

    def _pause(
        self,
        project: Path,
        staging: StagingWorktree,
        plan: WalkPlan,
        ran: tuple[str, ...],
        conflicts: tuple[str, ...],
    ) -> UpdateOutcome:
        """Bring the partial update back and record where to resume from.

        The layers finished so far, the paused layer included, are copied back
        with the paused layer's conflict markers and unmerged index entries. The
        conflict record names every layer's target and the finished layers; no
        lock is written.
        """
        staging.copy_back(paused=True)
        paused_at = ran[-1]
        UpdateRecorder(project, plan.lock).conflict(
            f"{plan.root}@{plan.targets[plan.root]}",
            _conflict_message(paused_at, conflicts),
            targets=plan.targets,
            finished=(*plan.skipped, *ran),
        )
        return UpdateOutcome(
            status=UpdateStatus.PAUSED,
            updated=ran,
            skipped=plan.skipped,
            paused_at=paused_at,
            conflicts=conflicts,
            warnings=plan.warnings,
        )
