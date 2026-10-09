"""Finish an update that was cut off after its walk, from its restore marker."""
# Spec: docs/design/06-project-lifecycle.md §Interrupted copy back

import logging
import tempfile
from pathlib import Path

from boilerplate.common.exceptions import UpdateTaskFailedError
from boilerplate.composition.staging.committed_lock import read_committed_lock
from boilerplate.composition.staging.finish_steps import FinishSteps
from boilerplate.composition.staging.finisher import Finisher
from boilerplate.composition.staging.unmerged_entries import list_unmerged_paths
from boilerplate.composition.updating.failed_task import FailedTask
from boilerplate.composition.updating.keep_or_undo import keep_or_undo
from boilerplate.composition.updating.layer_release import LayerRelease
from boilerplate.composition.updating.release_views import ReleaseViews
from boilerplate.composition.updating.task_failure_handler import TaskFailureHandler
from boilerplate.composition.updating.task_run import TaskRun
from boilerplate.composition.updating.task_runner import run_update_tasks
from boilerplate.composition.updating.update_options import UpdateOptions
from boilerplate.composition.updating.update_outcome import UpdateOutcome
from boilerplate.composition.updating.update_request import UpdateRequest
from boilerplate.composition.updating.update_status import UpdateStatus
from boilerplate.composition.updating.walk.layer_sources import read_layer_sources
from boilerplate.composition.updating.walk.paused_layers import paused_layers
from boilerplate.composition.updating.walk.target_releases import recorded_releases
from boilerplate.composition.updating.walk.update_lock_writer import write_update_lock
from boilerplate.composition.updating.walk.update_recorder import UpdateRecorder
from boilerplate.composition.updating.walk.update_walk import (
    conflict_message,
    update_failure_message,
)
from boilerplate.integrations.copier_types import TaskError
from boilerplate.models import BoilerplateLock, RestoreKind, RestoreMarker
from boilerplate.project_state.lock_file import read_lock
from boilerplate.repository.release_checkouts import ReleaseCheckouts
from boilerplate.types.serializable_version import SerializableVersion

_logger = logging.getLogger(__name__)


class InterruptedUpdate:
    """Finishes the update a restore marker describes, as rules 4 to 6 say.

    The cut-off run's files are already in the checkout, or are written again
    from the marker's result commit. What is left of the run follows from the
    marker's phase: the tasks, run again at the marker's targets, then the lock
    and the record; or the record alone of a paused run. The lock the run
    started from is the one at its starting commit, which HEAD still is.
    """

    def __init__(
        self,
        project: Path,
        marker: RestoreMarker,
        request: UpdateRequest,
        *,
        on_task_failure: TaskFailureHandler,
        boilerplate_version: str,
    ) -> None:
        """Prepare to finish the run `marker` describes.

        Args:
            project: The user's checkout.
            marker: The cut-off update's restore marker.
            request: What the user asked of this run; only how it runs the
                tasks applies, since the cut-off run's targets bind.
            on_task_failure: Decides what a failed task does to the update.
            boilerplate_version: The version of the tool, recorded in the lock.
        """
        self._project = project
        self._marker = marker
        self._request = request
        self._on_task_failure = on_task_failure
        self._boilerplate_version = boilerplate_version
        self._start = read_committed_lock(project, marker.start_commit)
        self._failed: FailedTask | None = None

    def finish(self) -> UpdateOutcome:
        """Finish the cut-off update.

        Returns:
            What the cut-off update ends as: updated, undone after a failed
            task, or paused on the conflict it recorded.

        Raises:
            UpdateTaskFailedError: If a task failed and the handler kept the
                files; the lock is written and the failure recorded first.
        """
        _logger.warning(
            "Finishing the update that was cut off earlier (moving to %s).",
            ", ".join(f"{layer}@{v}" for layer, v in self._marker.targets.items()),
        )
        if self._marker.kind is RestoreKind.PAUSED:
            return self._record_pause()
        with (
            ReleaseCheckouts() as checkouts,
            tempfile.TemporaryDirectory(
                prefix="boilerplate-views-", ignore_cleanup_errors=True
            ) as workdir,
        ):
            views = ReleaseViews(checkouts, workdir=Path(workdir))
            kept = Finisher(
                self._project,
                self._marker,
                FinishSteps(
                    write_record=self._record,
                    write_lock=lambda: self._write_lock(checkouts),
                    run_tasks=lambda: self._run_tasks(views),
                ),
            ).resume()
        if not kept:
            return self._outcome(UpdateStatus.UNDONE)
        if self._failed is not None:
            raise UpdateTaskFailedError(
                update_failure_message(self._failed),
                task=self._failed.command,
                remediation=self._failed.rerun,
            )
        return self._outcome(UpdateStatus.UPDATED)

    def _record_pause(self) -> UpdateOutcome:
        """Append the conflict record a paused run was cut off before."""
        finished = paused_layers(self._project, self._marker.targets)
        paused_at = finished[-1] if finished else self._root
        conflicts = list_unmerged_paths(self._project)
        Finisher(
            self._project,
            self._marker,
            FinishSteps(
                write_record=lambda: self._recorder().conflict(
                    self._root_specifier,
                    conflict_message(paused_at, conflicts),
                    targets=self._targets,
                    finished=finished,
                )
            ),
        ).resume()
        return UpdateOutcome(
            status=UpdateStatus.PAUSED,
            updated=finished,
            paused_at=paused_at,
            conflicts=conflicts,
        )

    @property
    def _root(self) -> str:
        """The walk's last layer, the composition's root, as the starting lock ends."""
        return self._start.layers[-1].name

    @property
    def _root_specifier(self) -> str:
        """The root layer at the version the cut-off run moved it to."""
        return f"{self._root}@{self._marker.targets[self._root]}"

    @property
    def _targets(self) -> dict[str, SerializableVersion]:
        """The marker's targets as versions."""
        return {
            layer: SerializableVersion(version)
            for layer, version in self._marker.targets.items()
        }

    def _recorder(self) -> UpdateRecorder:
        """Return a recorder of updates from the lock the run started from."""
        return UpdateRecorder(self._project, self._start)

    def _run_tasks(self, views: ReleaseViews) -> bool:
        """Run the composition's tasks at the marker's targets, as the walk would.

        A secret a task uses is asked again when the run prompts, since secrets
        are never recorded.

        Returns:
            Whether the files are kept.
        """
        if self._request.no_tasks:
            return True
        sources = read_layer_sources(self._project, self._start)
        releases = recorded_releases(sources, self._targets)
        root = self._root
        try:
            run_update_tasks(
                self._project,
                LayerRelease(layer=root, source=sources[root], ref=releases[root].ref),
                views.step_view(root, releases),
                TaskRun(tasks=tuple(views.tasks(releases)), secrets={}),
                UpdateOptions(
                    quiet=self._request.quiet,
                    interactive=self._request.interactive,
                    skip_answered=True,
                ),
            )
        except TaskError as error:
            failed = FailedTask.from_error(error)
            if not keep_or_undo(
                self._project, self._marker.start_commit, failed, self._on_task_failure
            ):
                return False
            self._failed = failed
        return True

    def _write_lock(self, checkouts: ReleaseCheckouts) -> None:
        """Write the lock at the targets, unless the cut-off run already did."""
        if _versions(read_lock(self._project)) == dict(self._marker.targets):
            return
        write_update_lock(
            self._project, self._start, self._boilerplate_version, checkouts
        )

    def _record(self) -> None:
        """Append ``success``, or ``failed`` after a task the user kept."""
        root_template = read_lock(self._project).root_template
        if self._failed is None:
            self._recorder().success(root_template)
        else:
            self._recorder().failed(root_template, update_failure_message(self._failed))

    def _outcome(self, status: UpdateStatus) -> UpdateOutcome:
        """Describe how the cut-off update ended."""
        return UpdateOutcome(status=status, updated=tuple(self._marker.targets))


def _versions(lock: BoilerplateLock) -> dict[str, str]:
    """Return each layer's version in `lock`, keyed by name."""
    return {entry.name: str(entry.version) for entry in lock.layers}
