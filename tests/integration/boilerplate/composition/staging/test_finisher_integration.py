"""The shared finisher of an update or an add, and the restore marker it keeps.

Design 06 §Staging worktree orders what follows the walk: a complete update runs
its tasks, then writes the lock and appends the record; §Add pipeline: an add runs
its tasks, then writes the lock and appends the record; §Step 5: a paused
update appends its conflict record and writes no lock. §Interrupted copy back:
the ref and then the marker are written before the copy back changes a file,
the phase advances as the run proceeds, and both are removed after the record.
"""

from pathlib import Path

import pytest

from boilerplate.common.exceptions import UpdateCopyBackFailedError
from boilerplate.composition.staging import (
    IntentJournal,
    IntentOperation,
    StagingWorktree,
)
from boilerplate.composition.staging.finish_steps import FinishSteps
from boilerplate.composition.staging.finisher import Finisher
from boilerplate.composition.staging.restore_marker_file import (
    RESTORE_REF,
    read_marker,
)
from boilerplate.models import (
    RestoreKind,
    RestoreMarker,
    RestoreOperation,
    RestorePhase,
)
from tests.boilerplate.templates.conftest import git
from tests.integration.boilerplate.composition.staging.conftest import head
from tests.integration.boilerplate.composition.staging.test_copy_back_failure_integration import (
    disk_full,
    restore_dying_after_one_file,
)

TARGETS = {"core": "1.1.0", "service": "1.2.0"}


class Seen:
    """What the steps saw of the marker and the ref while they ran."""

    def __init__(self, project: Path) -> None:
        self.project = project
        self.calls: list[str] = []
        self.markers: dict[str, RestoreMarker | None] = {}
        self.refs: dict[str, str] = {}

    def step(self, name: str) -> None:
        self.calls.append(name)
        self.markers[name] = read_marker(self.project)
        self.refs[name] = git(
            self.project, "for-each-ref", "--format=%(objectname)", RESTORE_REF
        ).strip()

    def steps(self, *, keep: bool = True) -> FinishSteps:
        def run_tasks() -> bool:
            self.step("tasks")
            return keep

        return FinishSteps(
            write_record=lambda: self.step("record"),
            write_lock=lambda: self.step("lock"),
            run_tasks=run_tasks,
        )


def staging(project: Path, root: Path, operation: IntentOperation) -> StagingWorktree:
    return StagingWorktree(project, operation=operation, temp_root=root)


def finish(
    project: Path,
    root: Path,
    seen: Seen,
    *,
    operation: RestoreOperation = RestoreOperation.UPDATE,
    kind: RestoreKind = RestoreKind.COMPLETE,
    keep: bool = True,
) -> tuple[str, bool]:
    """Stage a one-layer walk, copy it back and finish it; return its result commit."""
    with staging(project, root, IntentOperation(operation.value)) as stage:
        (stage.path / "added.txt").write_text("added\n", encoding="utf-8")
        result = stage.commit_layer("layer one")
        finisher = Finisher.for_staging(
            stage,
            operation=operation,
            kind=kind,
            targets=TARGETS,
            steps=seen.steps(keep=keep),
        )
        finisher.copy_back(stage)
        return result, finisher.finish()


class TestOrder:
    @pytest.mark.parametrize(
        ("operation", "kind", "order"),
        [
            pytest.param(
                RestoreOperation.UPDATE,
                RestoreKind.COMPLETE,
                ["tasks", "lock", "record"],
                id="update",
            ),
            pytest.param(
                RestoreOperation.ADD,
                RestoreKind.COMPLETE,
                ["tasks", "lock", "record"],
                id="add",
            ),
            pytest.param(
                RestoreOperation.UPDATE, RestoreKind.PAUSED, ["record"], id="paused"
            ),
        ],
    )
    def test_runs_the_steps_in_design_order(
        self,
        project: Path,
        staging_root: Path,
        operation: RestoreOperation,
        kind: RestoreKind,
        order: list[str],
    ) -> None:
        """Run each operation's steps in the order design 06 gives."""
        seen = Seen(project)

        finish(project, staging_root, seen, operation=operation, kind=kind)

        assert seen.calls == order

    def test_an_undone_update_writes_no_lock_and_no_record(
        self, project: Path, staging_root: Path
    ) -> None:
        """Stop after the tasks when they undo the update."""
        seen = Seen(project)

        _, kept = finish(project, staging_root, seen, keep=False)

        assert (kept, seen.calls) == (False, ["tasks"])


class TestJournal:
    def test_records_the_locking_phase_before_the_lock(
        self, project: Path, staging_root: Path
    ) -> None:
        """Name ``locking`` in the journal before the lock, as design 02 defines it."""
        phases: list[str] = []

        def write_lock() -> None:
            folder = next(staging_root.iterdir())
            phases.append(IntentJournal.read(folder).phase)

        with staging(project, staging_root, IntentOperation.UPDATE) as stage:
            stage.commit_layer("layer one")
            finisher = Finisher.for_staging(
                stage,
                operation=RestoreOperation.UPDATE,
                kind=RestoreKind.COMPLETE,
                targets=TARGETS,
                steps=FinishSteps(write_record=lambda: None, write_lock=write_lock),
            )
            finisher.copy_back(stage)
            finisher.finish()

        assert phases == ["locking"]


class TestMarker:
    def test_the_tasks_run_under_a_marker_of_the_run(
        self, project: Path, staging_root: Path
    ) -> None:
        """Describe the run in the marker while a complete update's tasks run."""
        seen = Seen(project)
        start = head(project)

        result, _ = finish(project, staging_root, seen)

        marker = seen.markers["tasks"]
        assert marker is not None
        assert (
            marker.operation,
            marker.kind,
            marker.phase,
            marker.start_commit,
            marker.result_commit,
            dict(marker.targets),
        ) == (
            RestoreOperation.UPDATE,
            RestoreKind.COMPLETE,
            RestorePhase.TASKS,
            start,
            result,
            TARGETS,
        )

    def test_the_ref_pins_the_result_while_the_run_finishes(
        self, project: Path, staging_root: Path
    ) -> None:
        """Keep the walk's result reachable through the per-worktree ref."""
        seen = Seen(project)

        result, _ = finish(project, staging_root, seen)

        assert seen.refs["tasks"] == result

    @pytest.mark.parametrize(
        ("operation", "kind", "step"),
        [
            pytest.param(
                RestoreOperation.UPDATE, RestoreKind.COMPLETE, "lock", id="update-lock"
            ),
            pytest.param(
                RestoreOperation.UPDATE,
                RestoreKind.COMPLETE,
                "record",
                id="update-record",
            ),
            pytest.param(
                RestoreOperation.ADD, RestoreKind.COMPLETE, "lock", id="add-lock"
            ),
            pytest.param(
                RestoreOperation.UPDATE, RestoreKind.PAUSED, "record", id="paused"
            ),
        ],
    )
    def test_the_lock_and_the_record_are_written_at_the_recording_phase(
        self,
        project: Path,
        staging_root: Path,
        operation: RestoreOperation,
        kind: RestoreKind,
        step: str,
    ) -> None:
        """Mark the phase ``recording`` until the record is appended."""
        seen = Seen(project)

        finish(project, staging_root, seen, operation=operation, kind=kind)

        marker = seen.markers[step]
        assert marker is not None
        assert marker.phase is RestorePhase.RECORDING

    def test_an_adds_tasks_run_at_the_tasks_phase(
        self, project: Path, staging_root: Path
    ) -> None:
        """Mark an add's tasks phase as an update's: its tasks run before its record."""
        seen = Seen(project)

        result, _ = finish(project, staging_root, seen, operation=RestoreOperation.ADD)

        marker = seen.markers["tasks"]
        assert marker is not None
        assert (marker.operation, marker.phase, seen.refs["tasks"]) == (
            RestoreOperation.ADD,
            RestorePhase.TASKS,
            result,
        )

    @pytest.mark.parametrize("keep", [True, False], ids=["finished", "undone"])
    def test_no_marker_and_no_ref_remain_after_the_run(
        self, project: Path, staging_root: Path, keep: bool
    ) -> None:
        """Remove the marker and then the ref once the run is over."""
        finish(project, staging_root, Seen(project), keep=keep)

        assert (read_marker(project), git(project, "for-each-ref", RESTORE_REF)) == (
            None,
            "",
        )

    def test_a_failed_copy_back_removes_the_marker_and_the_ref(
        self, project: Path, staging_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Remove both when the copy back fails and the checkout is restored."""
        monkeypatch.setattr(
            "boilerplate.composition.staging.copy_back.run_git",
            restore_dying_after_one_file(disk_full()),
        )

        with pytest.raises(UpdateCopyBackFailedError):
            finish(project, staging_root, Seen(project))

        assert (read_marker(project), git(project, "for-each-ref", RESTORE_REF)) == (
            None,
            "",
        )

    def test_an_interrupted_task_run_leaves_the_marker_at_the_tasks_phase(
        self, project: Path, staging_root: Path
    ) -> None:
        """Leave the marker for the next run when the run is cut off in its tasks."""

        def cut_off() -> bool:
            raise KeyboardInterrupt

        with (
            pytest.raises(KeyboardInterrupt),
            staging(project, staging_root, IntentOperation.UPDATE) as stage,
        ):
            (stage.path / "added.txt").write_text("added\n", encoding="utf-8")
            stage.commit_layer("layer one")
            finisher = Finisher.for_staging(
                stage,
                operation=RestoreOperation.UPDATE,
                kind=RestoreKind.COMPLETE,
                targets=TARGETS,
                steps=FinishSteps(write_record=lambda: None, run_tasks=cut_off),
            )
            finisher.copy_back(stage)
            finisher.finish()

        marker = read_marker(project)
        assert marker is not None
        assert marker.phase is RestorePhase.TASKS
