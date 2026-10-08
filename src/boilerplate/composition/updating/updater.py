"""The Application Layer component that walks an update across a project's layers."""
# Spec: docs/design/04-composition-engine.md §Safe Update

import logging
import tempfile
from pathlib import Path
from typing import Any

from boilerplate import __version__
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
