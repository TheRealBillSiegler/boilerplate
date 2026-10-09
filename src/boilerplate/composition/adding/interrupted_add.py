"""Finish an add that was cut off after its copy, from its restore marker."""
# Spec: docs/design/06-project-lifecycle.md §Interrupted copy back

import logging
import tempfile
from collections.abc import Callable
from pathlib import Path

from boilerplate.composition.adding.add_lock_writer import write_add_lock
from boilerplate.composition.adding.add_outcome import AddOutcome
from boilerplate.composition.adding.add_plan import AddPlan
from boilerplate.composition.adding.add_planner import plan_add
from boilerplate.composition.adding.add_recorder import AddRecorder
from boilerplate.composition.adding.add_request import AddRequest
from boilerplate.composition.adding.add_run import add_failure_message, record_add
from boilerplate.composition.adding.add_status import AddStatus
from boilerplate.composition.staging.committed_lock import read_committed_lock
from boilerplate.composition.staging.finish_steps import FinishSteps
from boilerplate.composition.staging.finisher import Finisher
from boilerplate.composition.updating.task_failure import TaskFailure
from boilerplate.composition.updating.task_failure_handler import TaskFailureHandler
from boilerplate.composition.updating.task_run import TaskRun
from boilerplate.composition.updating.task_runner import run_tasks
from boilerplate.composition.updating.update_options import UpdateOptions
from boilerplate.integrations.copier_types import load_answersfile_data
from boilerplate.models import BoilerplateLock, RestoreMarker
from boilerplate.project_state.lock_file import read_lock
from boilerplate.repository.release_checkouts import ReleaseCheckouts

_logger = logging.getLogger(__name__)


class InterruptedAdd:
    """Finishes the add a restore marker describes, as rules 4 to 6 say.

    The layer's files are already in the checkout, or are written again from
    the marker's result commit. What is left of the run follows from the
    marker's phase: the layer's tasks, run again, then the lock and the record;
    or the lock and the record alone. The release the layer was added at is
    the one its answers file records.
    """

    def __init__(
        self,
        project: Path,
        marker: RestoreMarker,
        request: AddRequest,
        *,
        on_task_failure: TaskFailureHandler,
        boilerplate_version: str,
    ) -> None:
        """Prepare to finish the run `marker` describes.

        Args:
            project: The user's checkout.
            marker: The cut-off add's restore marker.
            request: What the user asked of this run; only how it runs the
                tasks applies, since the cut-off run's layer binds.
            on_task_failure: Decides what a failed task does to the add.
            boilerplate_version: The version of the tool, recorded in the lock.
        """
        self._project = project
        self._marker = marker
        self._request = request
        self._failure = TaskFailure(on_task_failure)
        self._boilerplate_version = boilerplate_version
        ((self._layer, self._version),) = marker.targets.items()
        self._start = read_committed_lock(project, marker.start_commit)
        self._plan: AddPlan | None = None

    def finish(self) -> AddOutcome:
        """Finish the cut-off add.

        Returns:
            What the cut-off add ends as: added, or undone after a failed task.

        Raises:
            UpdateTaskFailedError: If a task failed and the handler kept the
                files; the lock is written and the failure recorded first.
        """
        _logger.warning(
            "Finishing the add of %s@%s that was cut off earlier.",
            self._layer,
            self._version,
        )
        with (
            ReleaseCheckouts() as checkouts,
            tempfile.TemporaryDirectory(
                prefix="boilerplate-views-", ignore_cleanup_errors=True
            ) as workdir,
        ):

            def planned() -> AddPlan:
                if self._plan is None:
                    self._plan = self._plan_add(checkouts, Path(workdir))
                return self._plan

            kept = Finisher(
                self._project,
                self._marker,
                FinishSteps(
                    write_record=lambda: record_add(
                        AddRecorder(self._project),
                        f"{self._layer}@{self._version}",
                        self._failure.failed,
                    ),
                    write_lock=lambda: self._write_lock(planned, checkouts),
                    run_tasks=lambda: self._run_tasks(planned),
                ),
            ).resume()
        if not kept:
            return self._outcome(AddStatus.UNDONE)
        self._failure.raise_if_failed(add_failure_message)
        return self._outcome(AddStatus.ADDED)

    def _plan_add(self, checkouts: ReleaseCheckouts, workdir: Path) -> AddPlan:
        """Plan the add again at the release the layer's answers file records."""
        recorded = load_answersfile_data(
            self._project, f".copier-answers.{self._layer}.yml"
        )
        return plan_add(
            self._project,
            AddRequest(
                name=self._layer,
                source=str(recorded["_src_path"]),
                ref=str(recorded["_commit"]),
            ),
            self._start,
            checkouts,
            workdir,
        )

    def _write_lock(
        self, planned: Callable[[], AddPlan], checkouts: ReleaseCheckouts
    ) -> None:
        """Write the lock with the layer last, unless the cut-off run already did."""
        if _lists(read_lock(self._project), self._layer, self._version):
            return
        write_add_lock(self._project, planned(), self._boilerplate_version, checkouts)

    def _run_tasks(self, planned: Callable[[], AddPlan]) -> bool:
        """Run the layer's own tasks once, as the cut-off add would have.

        A secret a task uses is asked again when the run prompts, since secrets
        are never recorded.

        Returns:
            Whether the files are kept.
        """
        if self._request.no_tasks:
            return True
        plan = planned()
        return self._failure.run(
            lambda: run_tasks(
                self._project,
                plan.release,
                plan.view,
                TaskRun(operation="copy", tasks=plan.tasks, secrets={}),
                UpdateOptions(
                    quiet=self._request.quiet,
                    interactive=self._request.interactive,
                    skip_answered=True,
                ),
            ),
            project=self._project,
            start_commit=self._marker.start_commit,
        )

    def _outcome(self, status: AddStatus) -> AddOutcome:
        """Describe how the cut-off add ended."""
        return AddOutcome(status=status, layer=self._layer, version=self._version)


def _lists(lock: BoilerplateLock, layer: str, version: str) -> bool:
    """Check whether `lock` lists `layer` at `version`."""
    return any(
        entry.name == layer and str(entry.version) == version for entry in lock.layers
    )
