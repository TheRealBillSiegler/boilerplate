"""A run cut off after its copy back leaves a restore marker the next run reads.

Design 06 §Interrupted copy back: the marker is written before the copy back
changes a file and removed after the record, so a run cut off in between leaves
it, and appends no record. The next ``update`` or ``add`` applies the marker
rules inside the operation lock, before anything reads the working tree.
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import NamedTuple

import pytest

from boilerplate.common.exceptions import (
    ActionRequiredError,
    UpdateInterruptedError,
    UpdateLayerDriftError,
    UpdateProjectNotReadyError,
)
from boilerplate.composition.adding import AddRequest, AddStatus, LayerAdder
from boilerplate.composition.staging.restore_marker_file import (
    read_marker,
    write_marker,
)
from boilerplate.composition.updating import Updater, UpdateRequest, UpdateStatus
from boilerplate.models import (
    MigrationRecord,
    MigrationStatus,
    RestoreKind,
    RestoreMarker,
    RestoreOperation,
    RestorePhase,
)
from boilerplate.project_state.lock_file import read_lock
from boilerplate.project_state.migrations_file import (
    MIGRATIONS_FILE,
    read_migrations,
)
from tests.boilerplate.templates.conftest import commit_all, git
from tests.integration.boilerplate.composition.adding.layers import build_layer
from tests.integration.boilerplate.composition.family import Family
from tests.integration.boilerplate.composition.scenarios.builders import (
    add_user_line,
    answers_file,
    append,
    compose_locked_family,
    lines,
)

BASE = {"core": "1.0.0", "service": "1.0.0"}
AFTER = {"core": "1.1.0", "service": "1.2.0"}
TASK = """_tasks:
  - command:
      - "{{ _copier_python }}"
      - -c
      - "print('ran', file=open('.tasked-marker', 'a', encoding='utf-8'))"
"""


def interrupted(*_args: object, **_kwargs: object) -> None:
    """Stand in for the task run, cut off by Ctrl-C as it starts."""
    raise KeyboardInterrupt


def statuses(project: Path) -> list[MigrationStatus]:
    return [record.status for record in read_migrations(project)]


def _marker_before(project: Path, started_at: datetime) -> RestoreMarker:
    """Build the marker an update to AFTER would leave if cut off as it recorded."""
    commit = git(project, "rev-parse", "HEAD").strip()
    return RestoreMarker(
        operation=RestoreOperation.UPDATE,
        kind=RestoreKind.COMPLETE,
        phase=RestorePhase.RECORDING,
        start_commit=commit,
        result_commit=commit,
        targets=AFTER,
        started_at=started_at,
    )


@pytest.fixture
def project(family: Family, tmp_path: Path) -> Path:
    """Compose core and service at their first releases, lock and commit."""
    return compose_locked_family(family, tmp_path, "service", BASE)


@pytest.fixture
def cut_off_update(project: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Update `project` and cut the run off right after the copy back."""
    monkeypatch.setattr(
        "boilerplate.composition.updating.walk.update_walk.run_tasks",
        interrupted,
    )
    with pytest.raises(KeyboardInterrupt):
        Updater().update(project, UpdateRequest(targets=AFTER))
    monkeypatch.undo()
    return project


class TestInterruptedUpdate:
    def test_leaves_a_marker_naming_every_target(self, cut_off_update: Path) -> None:
        """Keep the cut-off run's targets in the marker, in walk order."""
        marker = read_marker(cut_off_update)

        assert marker is not None
        assert dict(marker.targets) == AFTER

    def test_appends_no_record(self, cut_off_update: Path) -> None:
        """Keep the cut-off run's state out of the log: it holds finished runs only."""
        assert statuses(cut_off_update) == []

    def test_next_add_stops_naming_the_update(
        self, cut_off_update: Path, family: Family
    ) -> None:
        """Stop another command, naming the one to rerun (rule 3)."""
        with pytest.raises(UpdateInterruptedError) as stop:
            LayerAdder().add(
                cut_off_update,
                AddRequest(name="docs", source=family.repos["docs"].as_posix()),
            )

        assert "boilerplate update" in (stop.value.remediation or "")

    def test_next_run_stops_when_head_moved(self, cut_off_update: Path) -> None:
        """Stop when HEAD is no longer the run's starting commit (rule 3)."""
        git(cut_off_update, "add", ".copier-answers.core.yml")
        git(cut_off_update, "commit", "-q", "-m", "keep part of the update")

        with pytest.raises(UpdateInterruptedError, match=r"core@1\.1\.0"):
            Updater().update(cut_off_update, UpdateRequest(targets=AFTER))

    def test_a_committed_partial_update_meets_the_drift_rules(
        self, cut_off_update: Path
    ) -> None:
        """Drop the marker of a clean tree and plan afresh (rule 2)."""
        commit_all(cut_off_update, "keep the partial update")

        with pytest.raises(UpdateLayerDriftError):
            Updater().update(cut_off_update, UpdateRequest(targets=AFTER))

    def test_a_set_aside_partial_update_plans_afresh(
        self, cut_off_update: Path
    ) -> None:
        """Run a fresh update once the partial one is set aside (rule 2)."""
        git(cut_off_update, "reset", "-q")
        git(cut_off_update, "stash", "push", "-q", "--include-untracked")

        outcome = Updater().update(cut_off_update, UpdateRequest(targets=AFTER))

        assert (outcome.status, read_marker(cut_off_update)) == (
            UpdateStatus.UPDATED,
            None,
        )

    def test_a_finished_update_appends_one_success_record(self, project: Path) -> None:
        """Append exactly one record for a finished operation."""
        Updater().update(project, UpdateRequest(targets=AFTER))

        assert statuses(project) == [MigrationStatus.SUCCESS]

    def test_a_marker_whose_run_recorded_is_removed(self, project: Path) -> None:
        """Remove the marker of a run that appended its record (rule 1)."""
        Updater().update(project, UpdateRequest(targets=AFTER))
        record = read_migrations(project)[-1]
        stale = _marker_before(project, record.timestamp - timedelta(seconds=1))
        write_marker(project, stale)

        with pytest.raises(UpdateProjectNotReadyError):
            Updater().update(project, UpdateRequest(targets=AFTER))

        assert read_marker(project) is None


class TestInterruptedAdd:
    @pytest.fixture
    def tasked(self, project: Path) -> AddRequest:
        """Build a one-off layer with a task beside `project`; request adding it."""
        build_layer(project.parent, "tasked", copier=TASK)
        return AddRequest(
            name="tasked", source=(project.parent / "repos" / "tasked").as_posix()
        )

    @pytest.fixture
    def cut_off_add(
        self, project: Path, tasked: AddRequest, monkeypatch: pytest.MonkeyPatch
    ) -> Path:
        """Add the tasked layer and cut the run off as its tasks start."""
        monkeypatch.setattr(
            "boilerplate.composition.adding.add_run.run_tasks", interrupted
        )
        with pytest.raises(KeyboardInterrupt):
            LayerAdder().add(project, tasked)
        monkeypatch.undo()
        return project

    def test_leaves_a_marker_at_the_tasks_phase(self, cut_off_add: Path) -> None:
        """Keep the marker while the tasks run: an add passes the update's phases."""
        marker = read_marker(cut_off_add)

        assert marker is not None
        assert marker.phase is RestorePhase.TASKS

    def test_appends_no_record(self, cut_off_add: Path) -> None:
        """Write no record before the tasks: an add records after them."""
        assert statuses(cut_off_add) == []

    def test_the_rerun_finishes_the_add(
        self, cut_off_add: Path, tasked: AddRequest
    ) -> None:
        """Run the tasks, write the lock and append success (rule 5)."""
        outcome = LayerAdder().add(cut_off_add, tasked)

        assert (
            outcome.status,
            [entry.name for entry in read_lock(cut_off_add).layers][-1],
            statuses(cut_off_add),
        ) == (AddStatus.ADDED, "tasked", [MigrationStatus.SUCCESS])

    def test_the_rerun_runs_the_layers_tasks(
        self, cut_off_add: Path, tasked: AddRequest
    ) -> None:
        """Run the tasks the cut-off add never finished (rule 5)."""
        LayerAdder().add(cut_off_add, tasked)

        assert lines(cut_off_add / ".tasked-marker") == ["ran"]


def at_phase(project: Path, phase: RestorePhase) -> None:
    """Rewrite the project's marker at `phase`, as a run cut off there leaves it."""
    marker = read_marker(project)
    assert marker is not None
    write_marker(project, marker.at_phase(phase))


class TestFinishingACutOffUpdate:
    """The same update again finishes a run cut off after its walk (rules 4 to 6)."""

    def test_a_run_cut_off_in_its_tasks_is_finished(self, cut_off_update: Path) -> None:
        """Run the tasks again, write the lock and append success (rule 5)."""
        outcome = Updater().update(cut_off_update, UpdateRequest(targets=AFTER))

        assert (outcome.status, statuses(cut_off_update)) == (
            UpdateStatus.UPDATED,
            [MigrationStatus.SUCCESS],
        )

    def test_the_finished_run_runs_the_tasks(self, cut_off_update: Path) -> None:
        """Run the composition's tasks the cut-off run never ran (rule 5)."""
        Updater().update(cut_off_update, UpdateRequest(targets=AFTER))

        assert lines(cut_off_update / ".core-task-marker") == ["core task ran"]

    def test_the_finished_run_writes_the_lock_at_the_targets(
        self, cut_off_update: Path
    ) -> None:
        """Record the cut-off run's targets in the lock."""
        Updater().update(cut_off_update, UpdateRequest(targets=AFTER))

        lock = read_lock(cut_off_update)
        assert {entry.name: str(entry.version) for entry in lock.layers} == AFTER

    def test_the_finished_run_leaves_no_marker(self, cut_off_update: Path) -> None:
        """Remove the marker once the record is appended."""
        Updater().update(cut_off_update, UpdateRequest(targets=AFTER))

        assert read_marker(cut_off_update) is None

    def test_a_copy_back_cut_off_before_every_file_is_repeated(
        self, cut_off_update: Path
    ) -> None:
        """Repeat the copy back from the result commit (rule 4)."""
        at_phase(cut_off_update, RestorePhase.COPY_BACK)
        git(cut_off_update, "checkout", "--", ".copier-answers.core.yml")

        outcome = Updater().update(cut_off_update, UpdateRequest(targets=AFTER))

        assert (outcome.status, answers_file(cut_off_update, "core")["_commit"]) == (
            UpdateStatus.UPDATED,
            "1.1.0",
        )

    def test_a_copy_back_edited_since_stops(self, cut_off_update: Path) -> None:
        """Stop when a path differs from the result commit (rule 4)."""
        at_phase(cut_off_update, RestorePhase.COPY_BACK)
        append(cut_off_update / ".copier-answers.core.yml", "# my edit\n")

        with pytest.raises(UpdateInterruptedError, match="differs from its result"):
            Updater().update(cut_off_update, UpdateRequest(targets=AFTER))

    def test_a_run_cut_off_as_it_recorded_runs_no_tasks(
        self, cut_off_update: Path
    ) -> None:
        """Write the lock and the record only (rule 6)."""
        at_phase(cut_off_update, RestorePhase.RECORDING)

        Updater().update(cut_off_update, UpdateRequest(targets=AFTER))

        assert (
            statuses(cut_off_update),
            (cut_off_update / ".core-task-marker").exists(),
        ) == ([MigrationStatus.SUCCESS], False)


@pytest.fixture
def pause_cut_off_at_its_record(project: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Pause an update on service's conflict; cut the run off as it records."""
    add_user_line(project / "SERVICE.md")
    monkeypatch.setattr(
        "boilerplate.composition.updating.walk.update_walk.UpdateRecorder",
        interrupted,
    )
    with pytest.raises(KeyboardInterrupt):
        Updater().run(project, UpdateRequest(targets=AFTER))
    monkeypatch.undo()
    return project


class TestInterruptedPause:
    def test_the_marker_names_the_finished_and_the_paused_layers(
        self, pause_cut_off_at_its_record: Path
    ) -> None:
        """Keep core, which the walk finished, and service, whose merge conflicted.

        Design 02 §RestoreMarker: a paused run's marker holds the finished
        layers, in walk order, and the paused layer apart from them.
        """
        marker = read_marker(pause_cut_off_at_its_record)

        assert marker is not None
        assert (marker.finished, marker.paused_layer) == (("core",), "service")


class PausedRun(NamedTuple):
    """A paused update whose conflict record a crash took, and that record."""

    project: Path
    record: MigrationRecord


@pytest.fixture
def paused_before_its_record(project: Path) -> PausedRun:
    """Pause an update on a conflict, then undo its record as a crash would.

    The record is taken back out of the log and the marker the run held until
    then is written again, at the ``recording`` phase of a paused run.
    """
    add_user_line(project / "SERVICE.md")
    outcome = Updater().run(project, UpdateRequest(targets=AFTER))
    assert outcome.status is UpdateStatus.PAUSED
    (record,) = read_migrations(project)
    (project / MIGRATIONS_FILE).unlink()
    commit = git(project, "rev-parse", "HEAD").strip()
    write_marker(
        project,
        RestoreMarker(
            operation=RestoreOperation.UPDATE,
            kind=RestoreKind.PAUSED,
            phase=RestorePhase.RECORDING,
            start_commit=commit,
            result_commit=commit,
            targets=AFTER,
            finished=("core",),
            paused_layer="service",
            started_at=record.timestamp - timedelta(seconds=1),
        ),
    )
    return PausedRun(project, record)


class TestFinishingACutOffPause:
    def test_the_rerun_appends_the_conflict_record(
        self, paused_before_its_record: PausedRun
    ) -> None:
        """Append the paused run's conflict record, as it would have (rule 6)."""
        Updater().run(paused_before_its_record.project, UpdateRequest(targets=AFTER))

        (record,) = read_migrations(paused_before_its_record.project)
        original = paused_before_its_record.record
        assert (record.status, record.targets, record.finished) == (
            original.status,
            original.targets,
            original.finished,
        )

    def test_the_record_names_the_locks_root_whatever_the_marker_order(
        self, paused_before_its_record: PausedRun
    ) -> None:
        """Move from and to the root the lock ends with, not the marker's last key."""
        project = paused_before_its_record.project
        marker = read_marker(project)
        assert marker is not None
        root_first = dict(reversed(list(marker.targets.items())))
        write_marker(project, marker.model_copy(update={"targets": root_first}))

        Updater().run(project, UpdateRequest(targets=AFTER))

        (record,) = read_migrations(project)
        assert record.to_version == paused_before_its_record.record.to_version

    def test_the_rerun_ends_with_the_pause(
        self, paused_before_its_record: PausedRun
    ) -> None:
        """End with the paused run's exit: the conflict pause, code 4."""
        with pytest.raises(ActionRequiredError):
            Updater().update(
                paused_before_its_record.project, UpdateRequest(targets=AFTER)
            )

    def test_a_paused_copy_back_cut_off_stops(
        self, paused_before_its_record: PausedRun
    ) -> None:
        """Stop: no commit holds a paused run's conflicted files (rule 4)."""
        at_phase(paused_before_its_record.project, RestorePhase.COPY_BACK)

        with pytest.raises(UpdateInterruptedError, match="conflict had paused it"):
            Updater().update(
                paused_before_its_record.project, UpdateRequest(targets=AFTER)
            )


def cut_off_lock_write(*_args: object, **_kwargs: object) -> None:
    """Stand in for the add's lock write, cut off by Ctrl-C as it starts."""
    raise KeyboardInterrupt


class TestFinishingACutOffAdd:
    @pytest.fixture
    def cut_off_add(
        self, project: Path, monkeypatch: pytest.MonkeyPatch
    ) -> tuple[Path, AddRequest]:
        """Add a tasked layer with a file of its own; cut the run off at the lock."""
        build_layer(
            project.parent, "tasked", copier=TASK, files={"TASKED.md": "tasked\n"}
        )
        tasked = AddRequest(
            name="tasked", source=(project.parent / "repos" / "tasked").as_posix()
        )
        monkeypatch.setattr(
            "boilerplate.composition.adding.add_run.write_add_lock", cut_off_lock_write
        )
        with pytest.raises(KeyboardInterrupt):
            LayerAdder().add(project, tasked)
        monkeypatch.undo()
        return project, tasked

    def test_leaves_a_marker_at_the_recording_phase(
        self, cut_off_add: tuple[Path, AddRequest]
    ) -> None:
        """Mark an add's run ``recording`` once its tasks have run."""
        marker = read_marker(cut_off_add[0])

        assert marker is not None
        assert marker.phase is RestorePhase.RECORDING

    def test_the_rerun_writes_the_lock_and_the_record(
        self, cut_off_add: tuple[Path, AddRequest]
    ) -> None:
        """Finish the add: the lock lists the layer and success is recorded (rule 6)."""
        project, tasked = cut_off_add

        outcome = LayerAdder().add(project, tasked)

        assert (
            outcome.status,
            [entry.name for entry in read_lock(project).layers][-1],
            statuses(project),
        ) == (AddStatus.ADDED, "tasked", [MigrationStatus.SUCCESS])

    def test_the_rerun_runs_the_tasks_no_second_time(
        self, cut_off_add: tuple[Path, AddRequest]
    ) -> None:
        """Run no tasks at ``recording``: the cut-off add ran them (rule 6)."""
        project, tasked = cut_off_add

        LayerAdder().add(project, tasked)

        assert lines(project / ".tasked-marker") == ["ran"]

    def test_a_copy_back_cut_off_before_every_file_is_repeated(
        self, cut_off_add: tuple[Path, AddRequest]
    ) -> None:
        """Repeat the copy back from the result commit (rule 4).

        A run cut off in its copy back has run no task, so the file the task
        wrote goes with the rewound phase.
        """
        project, tasked = cut_off_add
        at_phase(project, RestorePhase.COPY_BACK)
        (project / ".tasked-marker").unlink()
        (project / ".copier-answers.tasked.yml").unlink()

        outcome = LayerAdder().add(project, tasked)

        assert (outcome.status, answers_file(project, "tasked")["_commit"]) == (
            AddStatus.ADDED,
            "1.0.0",
        )

    def test_an_update_stops_naming_the_add(
        self, cut_off_add: tuple[Path, AddRequest]
    ) -> None:
        """Stop another command, naming the one to rerun (rule 3)."""
        with pytest.raises(UpdateInterruptedError) as stop:
            Updater().update(cut_off_add[0], UpdateRequest(targets=AFTER))

        assert "boilerplate add" in (stop.value.remediation or "")
