"""Finish an update or an add after its walk: the copy back and what follows it."""
# Spec: docs/design/06-project-lifecycle.md §Interrupted copy back

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Self

from boilerplate.composition.staging.copy_back import restore_working_tree
from boilerplate.composition.staging.finish_steps import FinishSteps
from boilerplate.composition.staging.restore_marker_file import (
    pin_result,
    remove_marker,
    write_marker,
)
from boilerplate.composition.staging.staging_worktree import StagingWorktree
from boilerplate.composition.staging.walk_pause import WalkPause
from boilerplate.models import (
    RestoreKind,
    RestoreMarker,
    RestoreOperation,
    RestorePhase,
)


class Finisher:
    """Run what follows an update's or an add's walk under the restore marker.

    The copy back brings the walk's result into the user's checkout. A complete
    update or add then runs its tasks and writes its lock and its record. A
    paused update appends its conflict record only. What the lock, the record
    and the tasks are is the operation's own, passed in as callbacks.

    The restore marker brackets the copy back and what follows it up to the
    record: the ref that pins the walk's result is set and the marker written
    before the copy back changes a file, the marker's phase is rewritten as
    the run proceeds, and the marker and then the ref are removed after the
    record. A run cut off in between leaves the marker for the next run.
    """

    def __init__(
        self,
        project: Path,
        marker: RestoreMarker,
        steps: FinishSteps,
        *,
        journal: Callable[[str], None] | None = None,
        staging: StagingWorktree | None = None,
    ) -> None:
        """Prepare to finish the run `marker` describes.

        Args:
            project: The user's checkout.
            marker: The run's marker, at the phase the run has reached.
            steps: The operation's lock, record and tasks.
            journal: Records a phase in the staging's intent journal; it is
                told ``locking`` before the lock is written. ``None`` for a
                run that has no staging any more.
            staging: The staging whose walk ``copy_back`` brings into the
                checkout; ``None`` for a run that has no staging any more.
        """
        self._project = project
        self._marker = marker
        self._steps = steps
        self._journal = journal
        self._staging = staging
        self._begun = False

    @classmethod
    def for_staging(
        cls,
        staging: StagingWorktree,
        *,
        operation: RestoreOperation,
        targets: Mapping[str, str],
        steps: FinishSteps,
        paused: WalkPause | None = None,
    ) -> Self:
        """Prepare to finish the run whose walk `staging` holds.

        Args:
            staging: The active staging of the run, its walk done.
            operation: The command the run belongs to.
            targets: Each layer of the walk, in walk order, with its target
                version.
            steps: The operation's lock, record and tasks.
            paused: Where a conflict paused the walk; ``None`` when the walk
                finished every layer.

        Returns:
            The finisher, its marker at the ``copy_back`` phase.
        """
        return cls(
            staging.project,
            RestoreMarker(
                operation=operation,
                kind=RestoreKind.COMPLETE if paused is None else RestoreKind.PAUSED,
                phase=RestorePhase.COPY_BACK,
                start_commit=staging.start_commit,
                result_commit=staging.last_commit,
                targets=dict(targets),
                finished=() if paused is None else paused.finished,
                paused_layer=None if paused is None else paused.layer,
                started_at=staging.started_at,
            ),
            steps,
            journal=staging.record_phase,
            staging=staging,
        )

    def copy_back(self) -> None:
        """Mark the run, then copy the staging worktree back into the checkout.

        The ref is pinned and then the marker written once the checks have
        passed and before the first file of the checkout changes. A copy back
        that fails restores the checkout, so the marker and the ref go too;
        when that restore fails or is cut off, both stay at ``copy_back``, so
        the rerun can repeat the copy back or stop on the partial checkout.

        Raises:
            RuntimeError: If the finisher was built without a staging, as one
                is to resume a run whose staging is gone.
            UpdateCheckoutChangedError: If the checkout changed during staging.
            UpdatePathObstructedError: If a path the walk added already exists
                in the checkout as a file or directory git ignores.
            UpdateCopyBackFailedError: If the copy back failed after it began
                to write; the checkout is restored to the starting commit, or
                the error says it could not be.
        """
        staging = self._staging
        if staging is None:
            raise RuntimeError("This finisher has no staging to copy back.")
        try:
            staging.copy_back(
                paused=self._marker.kind is RestoreKind.PAUSED, on_start=self._begin
            )
        except BaseException:
            if self._begun and not staging.checkout_partly_written:
                remove_marker(self._project)
            raise

    def _begin(self) -> None:
        """Pin the walk's result, then write the marker, before the first file."""
        self._begun = True
        pin_result(self._project, self._marker.result_commit)
        write_marker(self._project, self._marker)

    def finish(self) -> bool:
        """Run the operation's steps that follow the copy back.

        Returns:
            Whether the files are kept: ``False`` when a task failed and the
            run was undone.
        """
        if self._marker.kind is RestoreKind.PAUSED:
            self._record()
            return True
        self._advance(RestorePhase.TASKS)
        if not _required(self._steps.run_tasks, "tasks")():
            remove_marker(self._project)
            return False
        self._record()
        return True

    def resume(self) -> bool:
        """Finish a cut-off run from the phase its marker records.

        At ``copy_back`` the copy back is repeated from the marker's result
        commit, which writes the same files on every run, and the run goes on
        as after a copy back. At ``tasks`` the tasks run again. At
        ``recording`` only the lock and the record remain.

        Returns:
            Whether the files are kept: ``False`` when a task failed and the
            run was undone.
        """
        marker = self._marker
        if marker.phase is RestorePhase.COPY_BACK:
            restore_working_tree(self._project, marker.result_commit)
        if marker.phase is RestorePhase.RECORDING:
            self._record()
            return True
        return self.finish()

    def _record(self) -> None:
        """Write the lock and the record under the ``recording`` phase, then unmark."""
        self._advance(RestorePhase.RECORDING)
        if self._marker.kind is RestoreKind.COMPLETE:
            if self._journal is not None:
                self._journal("locking")
            _required(self._steps.write_lock, "lock")()
        self._steps.write_record()
        remove_marker(self._project)

    def _advance(self, phase: RestorePhase) -> None:
        """Rewrite the marker at `phase`."""
        self._marker = self._marker.at_phase(phase)
        write_marker(self._project, self._marker)


def _required[Step](step: Step | None, name: str) -> Step:
    """Return the complete run's `step`, which only a paused run lacks."""
    if step is None:
        raise RuntimeError(f"A complete run needs its {name} step.")
    return step
