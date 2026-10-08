"""The migration records an update appends to the project's log."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from boilerplate.composition.updating.walk.update_recorder import UpdateRecorder
from boilerplate.models import BoilerplateLock, LockLayer, MigrationStatus
from boilerplate.project_state.migrations_file import read_migrations
from boilerplate.types import SerializableVersion

STAMP = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)


@pytest.fixture
def lock() -> BoilerplateLock:
    """Return a lock whose root template is ``app@1.0.0``."""
    return BoilerplateLock(
        boilerplate_version="0.3.0",
        copier_version="9.18.1",
        created_at=STAMP,
        updated_at=STAMP,
        root_template="app@1.0.0",
        layers=(
            LockLayer(
                name="app",
                version=SerializableVersion("1.0.0"),
                source="x",
                checksum="sha256:" + "a" * 64,
            ),
        ),
    )


class TestSuccess:
    def test_appends_a_success_record_from_the_locks_root_to_the_new_one(
        self, tmp_path: Path, lock: BoilerplateLock
    ) -> None:
        """Say which root template the update moved from and to."""
        UpdateRecorder(tmp_path, lock).success("app@1.1.0")

        (record,) = read_migrations(tmp_path)
        assert (record.status, record.from_version, record.to_version) == (
            MigrationStatus.SUCCESS,
            "app@1.0.0",
            "app@1.1.0",
        )

    def test_numbers_the_record_after_those_already_in_the_log(
        self, tmp_path: Path, lock: BoilerplateLock
    ) -> None:
        """Continue the sequence of the log."""
        recorder = UpdateRecorder(tmp_path, lock)
        recorder.success("app@1.1.0")

        recorder.success("app@1.2.0")

        assert [r.id for r in read_migrations(tmp_path)] == ["1", "2"]


class TestConflict:
    def test_names_each_layers_target_and_the_finished_layers(
        self, tmp_path: Path, lock: BoilerplateLock
    ) -> None:
        """Hold what a rerun resumes from."""
        UpdateRecorder(tmp_path, lock).conflict(
            "app@1.1.0",
            "README.md conflicted",
            targets={
                "core": SerializableVersion("2.0.0"),
                "app": SerializableVersion("1.1.0"),
            },
            finished=("core",),
        )

        (record,) = read_migrations(tmp_path)
        assert (record.status, record.targets, record.finished, record.error) == (
            MigrationStatus.CONFLICT,
            {"core": "2.0.0", "app": "1.1.0"},
            ("core",),
            "README.md conflicted",
        )


class TestFailed:
    def test_appends_a_failed_record_with_the_error(
        self, tmp_path: Path, lock: BoilerplateLock
    ) -> None:
        """Record the failed task's message."""
        UpdateRecorder(tmp_path, lock).failed("app@1.1.0", "task failed")

        (record,) = read_migrations(tmp_path)
        assert (record.status, record.error, record.to_version) == (
            MigrationStatus.FAILED,
            "task failed",
            "app@1.1.0",
        )
