"""The Application Layer component that adds one template layer to a project."""
# Spec: docs/design/06-project-lifecycle.md §Part 2: Project Update

import tempfile
from pathlib import Path

from boilerplate import __version__
from boilerplate.common.exceptions import LayerAlreadyAddedError, ProjectNotManagedError
from boilerplate.composition.adding.add_inputs import AddInputs
from boilerplate.composition.adding.add_outcome import AddOutcome
from boilerplate.composition.adding.add_planner import plan_add
from boilerplate.composition.adding.add_request import AddRequest
from boilerplate.composition.adding.add_run import AddRun
from boilerplate.composition.adding.interrupted_add import InterruptedAdd
from boilerplate.composition.staging import IntentOperation, check_project_ready
from boilerplate.composition.staging.operation_preflight import preflight
from boilerplate.composition.updating.task_failure_handler import (
    TaskFailureHandler,
    keep_files,
)
from boilerplate.models import RestoreOperation
from boilerplate.project_state.lock_file import LOCK_FILE_NAME, read_lock
from boilerplate.repository.release_checkouts import ReleaseCheckouts


class LayerAdder:
    """Adds one template layer to a project Boilerplate already manages.

    The result equals what one more by-hand ``copier copy`` of the layer, with
    its own answers file, would produce. The add checks every precondition before
    any staging folder exists. It then copies the layer into a detached worktree
    of the project, brings the result back into the user's checkout as the
    uncommitted changes plain Copier leaves, runs the layer's tasks once, and
    writes the lock with the layer last and the migration record.
    """

    def __init__(
        self,
        *,
        on_task_failure: TaskFailureHandler = keep_files,
        boilerplate_version: str = __version__,
        lock_timeout: float | None = None,
    ) -> None:
        """Prepare an adder.

        Args:
            on_task_failure: Called with the task that failed after the files
                were copied back; returns whether to keep the add or undo it.
                The default keeps it, as a caller that cannot ask does.
            boilerplate_version: The version of the tool, recorded in the lock.
            lock_timeout: Seconds to wait for another operation on the project
                to finish; ``BOILERPLATE_LOCK_TIMEOUT`` (default 60) when omitted.
        """
        self._on_task_failure = on_task_failure
        self._boilerplate_version = boilerplate_version
        self._lock_timeout = lock_timeout

    def add(self, project: Path, request: AddRequest) -> AddOutcome:
        """Add the requested layer to `project` and write its lock.

        Args:
            project: The project, a clean git repository root with a
                ``boilerplate.lock``.
            request: The layer to add and how to add it.

        Returns:
            What the add did: added, or undone after a failed task.

        Raises:
            ProjectNotManagedError: If the project has no ``boilerplate.lock``.
            UpdateProjectNotReadyError: If the project is dirty or not a
                repository root.
            UpdateSubmodulesUnsupportedError: If the project has submodules.
            LayerAlreadyAddedError: If the lock already lists the layer.
            AddAncestorsMissingError: If a layer the new layer extends is not in
                the lock.
            AddAncestorVersionError: If an ancestor's recorded version fails the
                new layer's ``extends`` reference.
            MetadataValidationError: If the template has no valid
                ``boilerplate.yml``.
            UpdateTaskFailedError: If a task failed and the files were kept.
            UpdateCheckoutChangedError: If the checkout changed during the add.
            ValueError: If Copier rejects a supplied answer; the error is
                Copier's own, not a ``BoilerplateError``.
            ConcurrencyContentionError: If another operation on the project
                still holds its lock when the timeout passes.
            UpdateInterruptedError: If a restore marker shows a run cut off
                after its walk that this one cannot finish.
            UpdatePathObstructedError: If a path the layer added already exists
                in the checkout as a file or directory git ignores.
        """
        with preflight(
            project, RestoreOperation.ADD, timeout=self._lock_timeout
        ) as interrupted:
            if interrupted is not None:
                return InterruptedAdd(
                    project,
                    interrupted,
                    request,
                    on_task_failure=self._on_task_failure,
                    boilerplate_version=self._boilerplate_version,
                ).finish()
            if not (project / LOCK_FILE_NAME).is_file():
                raise ProjectNotManagedError(
                    "Project is not managed by Boilerplate. "
                    "Use 'boilerplate adopt' first."
                )
            lock = read_lock(project)
            if any(entry.name == request.name for entry in lock.layers):
                raise LayerAlreadyAddedError(
                    f"Template '{request.name}' is already in this project. "
                    "Use 'boilerplate update' instead."
                )
            check_project_ready(project, IntentOperation.ADD)
            with (
                ReleaseCheckouts() as checkouts,
                tempfile.TemporaryDirectory(
                    prefix="boilerplate-views-", ignore_cleanup_errors=True
                ) as workdir,
            ):
                plan = plan_add(project, request, lock, checkouts, Path(workdir))
                return AddRun(
                    AddInputs(project, request, plan, checkouts),
                    on_task_failure=self._on_task_failure,
                    boilerplate_version=self._boilerplate_version,
                ).execute()
