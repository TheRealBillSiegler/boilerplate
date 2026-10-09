"""The restore-marker rules, against a git project and hand-written markers.

Design 06 §Interrupted copy back lists the rules in order; the first that
matches decides. Rule 1: the log's last record is the marked run's own. Rule 2:
the working tree is clean. Rule 3: the marker belongs to another command, or
HEAD moved.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from boilerplate.common.exceptions import UpdateInterruptedError
from boilerplate.composition.staging.restore_marker_file import (
    RESTORE_REF,
    pin_result,
    read_marker,
    write_marker,
)
from boilerplate.models import (
    MigrationRecord,
    MigrationStatus,
    RestoreKind,
    RestoreMarker,
    RestoreOperation,
    RestorePhase,
)
from boilerplate.project_state.interrupted_run import require_no_interrupted_run
from boilerplate.project_state.migrations_file import (
    append_migration,
    next_migration_id,
    read_migrations,
)
from tests.boilerplate.templates.conftest import commit_all, git, init_repo

STARTED = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)
TARGETS = {"core": "1.1.0", "service": "1.2.0"}


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Return a clean git project with one committed file."""
    root = tmp_path / "project"
    root.mkdir()
    init_repo(root)
    (root / "README.md").write_text("readme\n", encoding="utf-8")
    commit_all(root, "initial")
    return root


def head(project: Path) -> str:
    return git(project, "rev-parse", "HEAD").strip()


def mark(
    project: Path,
    *,
    operation: RestoreOperation = RestoreOperation.UPDATE,
    start_commit: str | None = None,
) -> RestoreMarker:
    """Write the marker a run to TARGETS leaves when cut off, and dirty the tree."""
    commit = head(project)
    marker = RestoreMarker(
        operation=operation,
        kind=RestoreKind.COMPLETE,
        phase=RestorePhase.RECORDING,
        start_commit=start_commit or commit,
        result_commit=commit,
        targets=TARGETS,
        started_at=STARTED,
    )
    pin_result(project, commit)
    write_marker(project, marker)
    (project / "README.md").write_text("restored\n", encoding="utf-8")
    return marker


def append(
    project: Path, status: MigrationStatus, at: datetime, **extra: object
) -> None:
    append_migration(
        project,
        MigrationRecord.model_validate(
            {
                "id": next_migration_id(read_migrations(project)),
                "from_version": "service@1.0.0",
                "to_version": "service@1.2.0",
                "timestamp": at,
                "status": status,
                **extra,
            }
        ),
    )


def ref_exists(project: Path) -> bool:
    return git(project, "for-each-ref", RESTORE_REF).strip() != ""


class TestNoMarker:
    def test_passes(self, project: Path) -> None:
        """Let a project no run was cut off in go on."""
        require_no_interrupted_run(project, RestoreOperation.UPDATE)

    def test_removes_a_ref_left_without_a_marker(self, project: Path) -> None:
        """Clear what a crash between pinning the ref and writing the marker left."""
        pin_result(project, head(project))

        require_no_interrupted_run(project, RestoreOperation.UPDATE)

        assert not ref_exists(project)


class TestRunFinished:
    def test_a_later_record_naming_the_last_layer_removes_the_marker(
        self, project: Path
    ) -> None:
        """Remove the marker of a run whose record names its last layer (rule 1)."""
        mark(project)
        append(project, MigrationStatus.SUCCESS, STARTED + timedelta(seconds=1))

        require_no_interrupted_run(project, RestoreOperation.UPDATE)

        assert (read_marker(project), ref_exists(project)) == (None, False)

    def test_a_later_conflict_record_with_the_same_targets_removes_it(
        self, project: Path
    ) -> None:
        """Match a conflict record on its targets (rule 1)."""
        mark(project)
        append(
            project,
            MigrationStatus.CONFLICT,
            STARTED + timedelta(seconds=1),
            targets=TARGETS,
            finished=["core"],
        )

        require_no_interrupted_run(project, RestoreOperation.UPDATE)

        assert read_marker(project) is None

    def test_a_record_from_before_the_run_does_not_count(self, project: Path) -> None:
        """Ignore a record older than the marker's start, so rule 3 stops the add."""
        mark(project)
        append(project, MigrationStatus.SUCCESS, STARTED - timedelta(seconds=1))

        with pytest.raises(UpdateInterruptedError):
            require_no_interrupted_run(project, RestoreOperation.ADD)

    def test_a_record_for_another_target_does_not_count(self, project: Path) -> None:
        """Ignore a record naming another version, so rule 3 stops the add."""
        mark(project)
        append(
            project,
            MigrationStatus.SUCCESS,
            STARTED + timedelta(seconds=1),
            to_version="service@9.0.0",
        )

        with pytest.raises(UpdateInterruptedError):
            require_no_interrupted_run(project, RestoreOperation.ADD)


class TestMarkerNoLongerBinds:
    def test_a_clean_tree_removes_the_marker(self, project: Path) -> None:
        """Remove the marker once the partial run was set aside (rule 2)."""
        mark(project)
        git(project, "checkout", "--", "README.md")

        require_no_interrupted_run(project, RestoreOperation.UPDATE)

        assert (read_marker(project), ref_exists(project)) == (None, False)


class TestAnotherRun:
    def test_another_command_stops_naming_the_one_to_rerun(self, project: Path) -> None:
        """Name the marker's command in the remediation (rule 3)."""
        mark(project, operation=RestoreOperation.ADD)

        with pytest.raises(UpdateInterruptedError) as stop:
            require_no_interrupted_run(project, RestoreOperation.UPDATE)

        assert "'boilerplate add'" in (stop.value.remediation or "")

    def test_a_moved_head_stops(self, project: Path) -> None:
        """Stop when HEAD is not the run's starting commit (rule 3)."""
        mark(project, start_commit="0" * 40)

        with pytest.raises(UpdateInterruptedError, match="HEAD"):
            require_no_interrupted_run(project, RestoreOperation.UPDATE)

    def test_the_stop_names_the_targets(self, project: Path) -> None:
        """Name every layer the cut-off run was moving, as design 07 asks."""
        mark(project, start_commit="0" * 40)

        with pytest.raises(UpdateInterruptedError) as stop:
            require_no_interrupted_run(project, RestoreOperation.UPDATE)

        assert stop.value.targets == TARGETS

    def test_the_stop_keeps_the_marker(self, project: Path) -> None:
        """Change nothing on a stop: the marker stays for the next run."""
        marker = mark(project, start_commit="0" * 40)

        with pytest.raises(UpdateInterruptedError):
            require_no_interrupted_run(project, RestoreOperation.UPDATE)

        assert read_marker(project) == marker
