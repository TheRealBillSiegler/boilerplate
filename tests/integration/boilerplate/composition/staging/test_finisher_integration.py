"""The shared finisher of an update or an add, and the restore marker it keeps.

Design 06 §Staging worktree orders what follows the walk: a complete update runs
its tasks, then writes the lock and appends the record; §Add pipeline: an add
does the same, its tasks before its lock and its record; §Step 5: a paused
update appends its conflict record and writes no lock. §Interrupted copy back:
the ref and then the marker are written before the copy back changes a file,
the phase advances as the run proceeds, and both are removed after the record.
"""

from pathlib import Path

import pytest

from boilerplate.common.exceptions import (
    UpdateCopyBackFailedError,
    UpdateInterruptedError,
)
from boilerplate.composition.staging import (
    IntentJournal,
    IntentOperation,
    StagingWorktree,
)
from boilerplate.composition.staging.finish_steps import FinishSteps
from boilerplate.composition.staging.finisher import Finisher
from boilerplate.composition.staging.restore_marker_file import (
    RESTORE_REF,
    pin_result,
    read_marker,
    write_marker,
)
from boilerplate.composition.staging.walk_pause import WalkPause
from boilerplate.models import (
    RestoreKind,
    RestoreMarker,
    RestoreOperation,
    RestorePhase,
)
from tests.boilerplate.templates.conftest import git
from tests.integration.boilerplate.composition.staging.conftest import (
    disk_full,
    file_in_use,
    head,
    restore_and_undo_dying,
    restore_dying_after_one_file,
)

TARGETS = {"core": "1.1.0", "service": "1.2.0"}
ADDED = {"docs": "1.0.0"}
FINISHED = ("core",)
PAUSED_AT = "service"


def targets_of(operation: RestoreOperation) -> dict[str, str]:
    """Return the walk's targets: an add walks only the layer it adds."""
    return ADDED if operation is RestoreOperation.ADD else TARGETS


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
            targets=targets_of(operation),
            steps=seen.steps(keep=keep),
            paused=(
                WalkPause(finished=FINISHED, layer=PAUSED_AT)
                if kind is RestoreKind.PAUSED
                else None
            ),
        )
        finisher.copy_back()
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

    @pytest.mark.parametrize("operation", list(RestoreOperation))
    def test_an_undone_run_writes_no_lock_and_no_record(
        self, project: Path, staging_root: Path, operation: RestoreOperation
    ) -> None:
        """Stop after the tasks when they undo the update or the add."""
        seen = Seen(project)

        _, kept = finish(project, staging_root, seen, operation=operation, keep=False)

        assert (kept, seen.calls) == (False, ["tasks"])


class TestIncompleteSteps:
    @pytest.mark.parametrize(
        ("steps", "missing"),
        [
            pytest.param(
                FinishSteps(write_record=lambda: None, write_lock=lambda: None),
                "tasks",
                id="no-tasks",
            ),
            pytest.param(
                FinishSteps(write_record=lambda: None, run_tasks=lambda: True),
                "lock",
                id="no-lock",
            ),
        ],
    )
    def test_a_complete_run_without_its_lock_or_tasks_is_refused(
        self,
        project: Path,
        staging_root: Path,
        steps: FinishSteps,
        missing: str,
    ) -> None:
        """Refuse a complete run that lacks a step design 06 gives it.

        Design 06 §Staging worktree: a complete run runs its tasks, then writes
        the lock and the record; only a paused run omits the first two.
        """
        with (
            staging(project, staging_root, IntentOperation.UPDATE) as stage,
            pytest.raises(RuntimeError, match=missing),
        ):
            stage.commit_layer("layer one")
            finisher = Finisher.for_staging(
                stage,
                operation=RestoreOperation.UPDATE,
                targets=TARGETS,
                steps=steps,
            )
            finisher.copy_back()
            finisher.finish()


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
                targets=TARGETS,
                steps=FinishSteps(
                    write_record=lambda: None,
                    write_lock=write_lock,
                    run_tasks=lambda: True,
                ),
            )
            finisher.copy_back()
            finisher.finish()

        assert phases == ["locking"]


class TestResumedFinisher:
    def test_a_finisher_built_without_a_staging_has_nothing_to_copy_back(
        self, project: Path, staging_root: Path
    ) -> None:
        """Refuse a copy back from a finisher that was built without a staging."""
        marker = cut_off_marker(
            project,
            staging_root,
            operation=RestoreOperation.UPDATE,
            phase=RestorePhase.TASKS,
        )

        with pytest.raises(RuntimeError, match="staging"):
            Finisher(project, marker, Seen(project).steps()).copy_back()


class TestMarker:
    @pytest.mark.parametrize("operation", list(RestoreOperation))
    def test_the_tasks_run_under_a_marker_of_the_run(
        self, project: Path, staging_root: Path, operation: RestoreOperation
    ) -> None:
        """Describe the run in the marker while a complete run's tasks run."""
        seen = Seen(project)
        start = head(project)

        result, _ = finish(project, staging_root, seen, operation=operation)

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
            operation,
            RestoreKind.COMPLETE,
            RestorePhase.TASKS,
            start,
            result,
            targets_of(operation),
        )

    def test_a_paused_run_marks_its_finished_layers_and_the_paused_one(
        self, project: Path, staging_root: Path
    ) -> None:
        """Keep a paused walk's layers in the marker, as design 02 §RestoreMarker."""
        seen = Seen(project)

        finish(project, staging_root, seen, kind=RestoreKind.PAUSED)

        marker = seen.markers["record"]
        assert marker is not None
        assert (marker.finished, marker.paused_layer) == (FINISHED, PAUSED_AT)

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
                RestoreOperation.ADD, RestoreKind.COMPLETE, "record", id="add-record"
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

    @pytest.mark.parametrize(
        ("undo_failure", "raised"),
        [
            pytest.param(file_in_use(), UpdateCopyBackFailedError, id="undo-fails"),
            pytest.param(KeyboardInterrupt(), KeyboardInterrupt, id="undo-cut-off"),
        ],
    )
    def test_a_failed_undo_keeps_the_marker_and_the_ref(
        self,
        project: Path,
        staging_root: Path,
        monkeypatch: pytest.MonkeyPatch,
        undo_failure: BaseException,
        raised: type[BaseException],
    ) -> None:
        """Keep both for the rerun when the checkout could not be restored.

        Design 06 removes them because the checkout is back at its pre-update
        state; here it is not, and rule 4 of the rerun needs the marker at
        ``copy_back`` and the ref pinning the result.
        """
        monkeypatch.setattr(
            "boilerplate.composition.staging.copy_back.run_git",
            restore_and_undo_dying(undo_failure),
        )

        with pytest.raises(raised):
            finish(project, staging_root, Seen(project))
        marker = read_marker(project)
        pinned = git(project, "for-each-ref", "--format=%(objectname)", RESTORE_REF)
        kept = (
            None
            if marker is None
            else (marker.phase, pinned.strip() == marker.result_commit)
        )

        assert kept == (RestorePhase.COPY_BACK, True)

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
                targets=TARGETS,
                steps=FinishSteps(
                    write_record=lambda: None,
                    write_lock=lambda: None,
                    run_tasks=cut_off,
                ),
            )
            finisher.copy_back()
            finisher.finish()

        marker = read_marker(project)
        assert marker is not None
        assert marker.phase is RestorePhase.TASKS


def cut_off_marker(
    project: Path, root: Path, *, operation: RestoreOperation, phase: RestorePhase
) -> RestoreMarker:
    """Stage a one-layer walk whose result adds a file; return its marker at `phase`.

    The staging is gone afterwards and the checkout is clean, as after a run
    whose copy back a crash cut off before it wrote a file.
    """
    with staging(project, root, IntentOperation(operation.value)) as stage:
        (stage.path / "added.txt").write_text("added\n", encoding="utf-8")
        marker = RestoreMarker(
            operation=operation,
            kind=RestoreKind.COMPLETE,
            phase=phase,
            start_commit=stage.start_commit,
            result_commit=stage.commit_layer("layer one"),
            targets=targets_of(operation),
            started_at=stage.started_at,
        )
    pin_result(project, marker.result_commit)
    write_marker(project, marker)
    return marker


def ignore(project: Path, pattern: str) -> None:
    """Make git ignore `pattern` in `project` through its own exclude file."""
    exclude = project / ".git" / "info" / "exclude"
    exclude.parent.mkdir(exist_ok=True)
    with exclude.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(f"{pattern}\n")


class TestResume:
    @pytest.mark.parametrize(
        ("operation", "phase", "order"),
        [
            pytest.param(
                RestoreOperation.UPDATE,
                RestorePhase.COPY_BACK,
                ["tasks", "lock", "record"],
                id="update-copy-back",
            ),
            pytest.param(
                RestoreOperation.UPDATE,
                RestorePhase.TASKS,
                ["tasks", "lock", "record"],
                id="update-tasks",
            ),
            pytest.param(
                RestoreOperation.UPDATE,
                RestorePhase.RECORDING,
                ["lock", "record"],
                id="update-recording",
            ),
            pytest.param(
                RestoreOperation.ADD,
                RestorePhase.COPY_BACK,
                ["tasks", "lock", "record"],
                id="add-copy-back",
            ),
            pytest.param(
                RestoreOperation.ADD,
                RestorePhase.TASKS,
                ["tasks", "lock", "record"],
                id="add-tasks",
            ),
            pytest.param(
                RestoreOperation.ADD,
                RestorePhase.RECORDING,
                ["lock", "record"],
                id="add-recording",
            ),
        ],
    )
    def test_runs_what_is_left_of_the_run(
        self,
        project: Path,
        staging_root: Path,
        operation: RestoreOperation,
        phase: RestorePhase,
        order: list[str],
    ) -> None:
        """Run the steps after the marker's phase, as design 06 rules 4 to 6 say."""
        marker = cut_off_marker(project, staging_root, operation=operation, phase=phase)
        seen = Seen(project)

        Finisher(project, marker, seen.steps()).resume()

        assert seen.calls == order

    def test_a_cut_off_copy_back_is_repeated_from_the_result(
        self, project: Path, staging_root: Path
    ) -> None:
        """Write the result commit's files again before the tasks (rule 4)."""
        marker = cut_off_marker(
            project,
            staging_root,
            operation=RestoreOperation.UPDATE,
            phase=RestorePhase.COPY_BACK,
        )
        seen = Seen(project)

        Finisher(project, marker, seen.steps()).resume()

        assert (project / "added.txt").read_text(encoding="utf-8") == "added\n"

    def test_an_ignored_file_made_at_an_added_path_stops_the_repeat(
        self, project: Path, staging_root: Path
    ) -> None:
        """Stop before a repeated copy back overwrites an ignored file (rule 4).

        The status check cannot see the file, since git ignores it, so the
        repeat compares each path the run adds with the result commit's blob.
        """
        marker = cut_off_marker(
            project,
            staging_root,
            operation=RestoreOperation.UPDATE,
            phase=RestorePhase.COPY_BACK,
        )
        ignore(project, "added.txt")
        (project / "added.txt").write_bytes(b"mine\n")
        seen = Seen(project)

        with pytest.raises(UpdateInterruptedError, match=r"added\.txt"):
            Finisher(project, marker, seen.steps()).resume()

        assert ((project / "added.txt").read_bytes(), seen.calls) == (b"mine\n", [])

    def test_an_ignored_file_the_cut_off_run_wrote_is_repeated(
        self, project: Path, staging_root: Path
    ) -> None:
        """Repeat the copy back over an ignored file that already holds its result."""
        marker = cut_off_marker(
            project,
            staging_root,
            operation=RestoreOperation.UPDATE,
            phase=RestorePhase.COPY_BACK,
        )
        ignore(project, "added.txt")
        (project / "added.txt").write_bytes(b"added\n")
        seen = Seen(project)

        Finisher(project, marker, seen.steps()).resume()

        assert seen.calls == ["tasks", "lock", "record"]

    def test_no_marker_remains_after_the_resumed_run(
        self, project: Path, staging_root: Path
    ) -> None:
        """Remove the marker and then the ref once the resumed run recorded."""
        marker = cut_off_marker(
            project,
            staging_root,
            operation=RestoreOperation.UPDATE,
            phase=RestorePhase.TASKS,
        )

        Finisher(project, marker, Seen(project).steps()).resume()

        assert (read_marker(project), git(project, "for-each-ref", RESTORE_REF)) == (
            None,
            "",
        )
