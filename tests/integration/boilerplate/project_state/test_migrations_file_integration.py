"""The migration log through the real filesystem across several operations."""

from datetime import UTC, datetime
from pathlib import Path

from boilerplate.models import MigrationRecord, MigrationStatus
from boilerplate.project_state.migrations_file import (
    append_migration,
    next_migration_id,
    read_migrations,
)

STAMP = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)


def _append(project: Path, **fields: object) -> MigrationRecord:
    record = MigrationRecord.model_validate(
        {
            "id": next_migration_id(read_migrations(project)),
            "to_version": "app@1.1.0",
            "timestamp": STAMP,
            **fields,
        }
    )
    append_migration(project, record)
    return record


class TestAuditLogLifecycle:
    """A create, a paused update and its rerun leave three ordered records."""

    def test_a_pause_and_its_rerun_are_both_recorded(self, tmp_path: Path) -> None:
        _append(tmp_path, status="created", to_version="app@1.0.0")
        paused = _append(
            tmp_path,
            status="conflict",
            from_version="app@1.0.0",
            classification="MINOR",
            targets={"core": "2.0.0", "app": "1.1.0"},
            finished=["core"],
        )
        _append(
            tmp_path, status="success", from_version="app@1.0.0", classification="MINOR"
        )

        records = read_migrations(tmp_path)

        assert [(r.id, r.status) for r in records] == [
            ("1", MigrationStatus.CREATED),
            ("2", MigrationStatus.CONFLICT),
            ("3", MigrationStatus.SUCCESS),
        ]
        assert records[1] == paused
