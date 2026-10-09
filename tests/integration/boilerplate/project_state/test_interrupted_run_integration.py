"""The restore-marker rules, against a git project and hand-written markers.

Design 06 §Interrupted copy back lists the rules in order; the first that
matches decides. Rule 1: the log's last record is the marked run's own. Rule 2:
the working tree is clean. Rule 3: the marker belongs to another command, or
HEAD moved. Rules 4 to 6 hand a run cut off in its copy back, its tasks or its
record back to be finished; a copy back only when it can be repeated.
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
    BoilerplateLock,
    LockLayer,
    MigrationRecord,
    MigrationStatus,
    RestoreKind,
    RestoreMarker,
    RestoreOperation,
    RestorePhase,
)
from boilerplate.project_state.interrupted_run import resolve_interrupted_run
from boilerplate.project_state.lock_file import write_lock
from boilerplate.project_state.migrations_file import (
    append_migration,
    next_migration_id,
    read_migrations,
)
from boilerplate.types import SerializableVersion
from tests.boilerplate.templates.conftest import commit_all, git, init_repo

STARTED = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)
TARGETS = {"core": "1.1.0", "service": "1.2.0"}
ADDED = {"docs": "1.0.0"}


def _lock_layer(name: str) -> LockLayer:
    return LockLayer(
        name=name,
        version=SerializableVersion("1.0.0"),
        source=f"https://example.com/{name}.git",
        checksum="sha256:" + "a" * 64,
    )


LOCK = BoilerplateLock(
    boilerplate_version="0.3.0",
    copier_version="9.18.1",
    created_at=STARTED - timedelta(days=1),
    updated_at=STARTED - timedelta(days=1),
    root_template="service@1.0.0",
    layers=(_lock_layer("core"), _lock_layer("service")),
)
"""The lock the runs start from: core, then the root service, in walk order."""


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Return a clean git project with a committed lock and one other file."""
    root = tmp_path / "project"
    root.mkdir()
    init_repo(root)
    (root / "README.md").write_text("readme\n", encoding="utf-8")
    write_lock(root, LOCK)
    commit_all(root, "initial")
    return root


def head(project: Path) -> str:
    return git(project, "rev-parse", "HEAD").strip()


def mark(
    project: Path,
    *,
    operation: RestoreOperation = RestoreOperation.UPDATE,
    start_commit: str | None = None,
    targets: dict[str, str] | None = None,
) -> RestoreMarker:
    """Write the marker a run to TARGETS leaves when cut off, and dirty the tree.

    An add walks only the layer it adds, so its marker names ADDED instead.
    """
    commit = head(project)
    marker = RestoreMarker(
        operation=operation,
        kind=RestoreKind.COMPLETE,
        phase=RestorePhase.RECORDING,
        start_commit=start_commit or commit,
        result_commit=commit,
        targets=targets or (ADDED if operation is RestoreOperation.ADD else TARGETS),
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
        resolve_interrupted_run(project, RestoreOperation.UPDATE)

    def test_removes_a_ref_left_without_a_marker(self, project: Path) -> None:
        """Clear what a crash between pinning the ref and writing the marker left."""
        pin_result(project, head(project))

        resolve_interrupted_run(project, RestoreOperation.UPDATE)

        assert not ref_exists(project)


class TestRunFinished:
    def test_a_later_record_naming_the_last_layer_removes_the_marker(
        self, project: Path
    ) -> None:
        """Remove the marker of a run whose record names its last layer (rule 1)."""
        mark(project)
        append(project, MigrationStatus.SUCCESS, STARTED + timedelta(seconds=1))

        resolve_interrupted_run(project, RestoreOperation.UPDATE)

        assert (read_marker(project), ref_exists(project)) == (None, False)

    def test_the_last_layer_is_the_locks_root_not_the_last_key(
        self, project: Path
    ) -> None:
        """Find the walk's last layer in the starting lock, not by key order (rule 1).

        The marker names the root first here, as a record read back with sorted
        keys would for a root that sorts before its ancestor.
        """
        mark(project, targets={"service": "1.2.0", "core": "1.1.0"})
        append(project, MigrationStatus.SUCCESS, STARTED + timedelta(seconds=1))

        resolve_interrupted_run(project, RestoreOperation.UPDATE)

        assert read_marker(project) is None

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

        resolve_interrupted_run(project, RestoreOperation.UPDATE)

        assert read_marker(project) is None

    def test_a_record_from_before_the_run_does_not_count(self, project: Path) -> None:
        """Ignore a record older than the marker's start, so rule 3 stops the add."""
        mark(project)
        append(project, MigrationStatus.SUCCESS, STARTED - timedelta(seconds=1))

        with pytest.raises(UpdateInterruptedError):
            resolve_interrupted_run(project, RestoreOperation.ADD)

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
            resolve_interrupted_run(project, RestoreOperation.ADD)


class TestMarkerNoLongerBinds:
    def test_a_clean_tree_removes_the_marker(self, project: Path) -> None:
        """Remove the marker once the partial run was set aside (rule 2)."""
        mark(project)
        git(project, "checkout", "--", "README.md")

        resolve_interrupted_run(project, RestoreOperation.UPDATE)

        assert (read_marker(project), ref_exists(project)) == (None, False)


class TestAnotherRun:
    def test_another_command_stops_naming_the_one_to_rerun(self, project: Path) -> None:
        """Name the marker's command in the remediation (rule 3)."""
        mark(project, operation=RestoreOperation.ADD)

        with pytest.raises(UpdateInterruptedError) as stop:
            resolve_interrupted_run(project, RestoreOperation.UPDATE)

        assert "'boilerplate add'" in (stop.value.remediation or "")

    def test_a_moved_head_stops(self, project: Path) -> None:
        """Stop when HEAD is not the run's starting commit (rule 3)."""
        mark(project, start_commit="0" * 40)

        with pytest.raises(UpdateInterruptedError, match="HEAD"):
            resolve_interrupted_run(project, RestoreOperation.UPDATE)

    def test_the_stop_names_the_targets(self, project: Path) -> None:
        """Name every layer the cut-off run was moving, as design 07 asks."""
        mark(project, start_commit="0" * 40)

        with pytest.raises(UpdateInterruptedError) as stop:
            resolve_interrupted_run(project, RestoreOperation.UPDATE)

        assert stop.value.targets == TARGETS

    def test_the_stop_keeps_the_marker(self, project: Path) -> None:
        """Change nothing on a stop: the marker stays for the next run."""
        marker = mark(project, start_commit="0" * 40)

        with pytest.raises(UpdateInterruptedError):
            resolve_interrupted_run(project, RestoreOperation.UPDATE)

        assert read_marker(project) == marker


def result_commit(project: Path) -> str:
    """Commit an edit and an added file on a side branch; return the commit.

    The checkout goes back to where it was, clean, as the staging worktree
    leaves the user's checkout while it walks.
    """
    git(project, "switch", "-q", "-c", "result")
    (project / "README.md").write_text("result\n", encoding="utf-8")
    (project / "added.txt").write_text("added\n", encoding="utf-8")
    commit_all(project, "result")
    commit = head(project)
    git(project, "switch", "-q", "-")
    return commit


def mark_copy_back(
    project: Path, result: str, paused_layer: str | None = None
) -> RestoreMarker:
    """Write the marker of a run cut off in its copy back from `result`.

    A run with a `paused_layer` is one a conflict paused there.
    """
    marker = RestoreMarker(
        operation=RestoreOperation.UPDATE,
        kind=RestoreKind.COMPLETE if paused_layer is None else RestoreKind.PAUSED,
        phase=RestorePhase.COPY_BACK,
        start_commit=head(project),
        result_commit=result,
        targets=TARGETS,
        paused_layer=paused_layer,
        started_at=STARTED,
    )
    pin_result(project, result)
    write_marker(project, marker)
    return marker


class TestRunToFinish:
    @pytest.mark.parametrize("phase", [RestorePhase.TASKS, RestorePhase.RECORDING])
    def test_a_run_cut_off_after_its_copy_back_is_handed_back(
        self, project: Path, phase: RestorePhase
    ) -> None:
        """Return the marker of a run cut off in its tasks or its record (5, 6)."""
        marker = mark(project).at_phase(phase)
        write_marker(project, marker)

        assert resolve_interrupted_run(project, RestoreOperation.UPDATE) == marker

    def test_a_copy_back_that_wrote_its_result_is_handed_back(
        self, project: Path
    ) -> None:
        """Return the marker when every changed path matches the result (rule 4)."""
        result = result_commit(project)
        marker = mark_copy_back(project, result)
        git(project, "restore", f"--source={result}", "--worktree", "--", ":/")

        assert resolve_interrupted_run(project, RestoreOperation.UPDATE) == marker

    def test_a_copy_back_cut_off_partway_is_handed_back(self, project: Path) -> None:
        """Accept a path the copy back had not written yet: it still matches HEAD."""
        result = result_commit(project)
        marker = mark_copy_back(project, result)
        git(project, "restore", f"--source={result}", "--worktree", "--", "added.txt")

        assert resolve_interrupted_run(project, RestoreOperation.UPDATE) == marker

    def test_an_edit_since_the_copy_back_stops(self, project: Path) -> None:
        """Stop when a changed path differs from the result commit (rule 4)."""
        result = result_commit(project)
        mark_copy_back(project, result)
        git(project, "restore", f"--source={result}", "--worktree", "--", ":/")
        (project / "added.txt").write_text("edited since\n", encoding="utf-8")

        with pytest.raises(UpdateInterruptedError, match="differs from its result"):
            resolve_interrupted_run(project, RestoreOperation.UPDATE)

    def test_a_paused_copy_back_stops(self, project: Path) -> None:
        """Stop a paused copy back, whose conflicted files no commit holds (rule 4)."""
        result = result_commit(project)
        mark_copy_back(project, result, paused_layer="core")
        git(project, "restore", f"--source={result}", "--worktree", "--", ":/")

        with pytest.raises(UpdateInterruptedError, match="conflict had paused it"):
            resolve_interrupted_run(project, RestoreOperation.UPDATE)
