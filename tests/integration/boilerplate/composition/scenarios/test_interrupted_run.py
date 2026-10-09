"""A run cut off after its copy back leaves a restore marker the next run reads.

Design 06 §Interrupted copy back: the marker is written before the copy back
changes a file and removed after the record, so a run cut off in between leaves
it, and appends no record. The next ``update`` or ``add`` applies the marker
rules inside the operation lock, before anything reads the working tree.
"""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from boilerplate.common.exceptions import (
    UpdateInterruptedError,
    UpdateLayerDriftError,
    UpdateProjectNotReadyError,
)
from boilerplate.composition.adding import AddRequest, LayerAdder
from boilerplate.composition.staging.restore_marker_file import (
    read_marker,
    write_marker,
)
from boilerplate.composition.updating import Updater, UpdateRequest, UpdateStatus
from boilerplate.models import (
    MigrationStatus,
    RestoreKind,
    RestoreMarker,
    RestoreOperation,
    RestorePhase,
)
from boilerplate.project_state.migrations_file import read_migrations
from tests.boilerplate.templates.conftest import commit_all, git
from tests.integration.boilerplate.composition.adding.layers import build_layer
from tests.integration.boilerplate.composition.family import Family
from tests.integration.boilerplate.composition.scenarios.builders import (
    compose_locked_family,
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
        "boilerplate.composition.updating.walk.update_walk.run_update_tasks",
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
            "boilerplate.composition.adding.add_run.run_add_tasks", interrupted
        )
        with pytest.raises(KeyboardInterrupt):
            LayerAdder().add(project, tasked)
        monkeypatch.undo()
        return project

    def test_leaves_a_marker_at_the_tasks_phase(self, cut_off_add: Path) -> None:
        """Keep the marker while the tasks run: an add passes the update's phases."""
        marker = read_marker(cut_off_add)

        assert marker is not None
        assert (marker.operation, marker.phase) == (
            RestoreOperation.ADD,
            RestorePhase.TASKS,
        )

    def test_appends_no_record(self, cut_off_add: Path) -> None:
        """Write no record before the tasks: an add records after them."""
        assert statuses(cut_off_add) == []

    def test_the_rerun_stops_with_the_interrupted_error(
        self, cut_off_add: Path, tasked: AddRequest
    ) -> None:
        """Stop the same command on the marker its working tree still holds."""
        with pytest.raises(UpdateInterruptedError):
            LayerAdder().add(cut_off_add, tasked)
