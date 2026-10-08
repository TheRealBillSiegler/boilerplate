"""Tests for reading and appending ``.boilerplate/migrations.yml``."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from boilerplate.models import MigrationRecord, MigrationStatus
from boilerplate.project_state.migrations_file import (
    MIGRATIONS_FILE,
    append_migration,
    next_migration_id,
    read_migrations,
)

STAMP = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)


def _record(record_id: str, **overrides: object) -> MigrationRecord:
    fields: dict[str, object] = {
        "id": record_id,
        "from_version": "app@1.0.0",
        "to_version": "app@1.1.0",
        "timestamp": STAMP,
        "status": "success",
        "classification": "MINOR",
        **overrides,
    }
    return MigrationRecord.model_validate(fields)


def _conflict(record_id: str) -> MigrationRecord:
    return _record(
        record_id,
        status="conflict",
        targets={"core": "2.0.0", "service": "1.0.0"},
        finished=["core"],
    )


class TestReadMigrations:
    """The audit log reads back in the order it was written."""

    def test_a_project_without_the_file_has_no_history(self, tmp_path: Path) -> None:
        assert read_migrations(tmp_path) == ()

    def test_reads_what_was_appended_in_order(self, tmp_path: Path) -> None:
        first = _record("1", status="created", from_version=None, classification=None)
        append_migration(tmp_path, first)
        append_migration(tmp_path, _record("2"))

        assert [r.id for r in read_migrations(tmp_path)] == ["1", "2"]
        assert read_migrations(tmp_path)[0] == first

    def test_a_conflict_record_keeps_its_targets_and_finished_layers(
        self, tmp_path: Path
    ) -> None:
        append_migration(tmp_path, _conflict("1"))

        (record,) = read_migrations(tmp_path)

        assert record.status is MigrationStatus.CONFLICT
        assert record.targets == {"core": "2.0.0", "service": "1.0.0"}
        assert record.finished == ("core",)

    @pytest.mark.parametrize(
        "text",
        ["- id: [unclosed\n", "not: a list\n", "- id: '0'\n  to_version: x\n", ""],
        ids=["unparseable", "not-a-list", "invalid-record", "empty"],
    )
    def test_a_corrupted_file_reads_as_empty_history_and_warns(
        self, tmp_path: Path, mocker: MockerFixture, text: str
    ) -> None:
        warning = mocker.patch("boilerplate.project_state.migrations_file._logger")
        (tmp_path / MIGRATIONS_FILE).parent.mkdir()
        (tmp_path / MIGRATIONS_FILE).write_text(text, encoding="utf-8")

        assert read_migrations(tmp_path) == ()
        assert warning.warning.called is (text != "")


class TestAppendMigration:
    """An append adds one record and leaves the earlier ones as they were."""

    def test_creates_the_boilerplate_directory_and_file(self, tmp_path: Path) -> None:
        append_migration(tmp_path, _record("1"))

        assert (tmp_path / ".boilerplate" / "migrations.yml").is_file()

    def test_leaves_earlier_records_untouched(self, tmp_path: Path) -> None:
        append_migration(tmp_path, _record("1"))
        before = read_migrations(tmp_path)

        append_migration(tmp_path, _record("2", status="failed", error="boom"))

        assert read_migrations(tmp_path)[:1] == before

    def test_leaves_no_temporary_file_behind(self, tmp_path: Path) -> None:
        append_migration(tmp_path, _record("1"))

        assert [p.name for p in (tmp_path / ".boilerplate").iterdir()] == [
            "migrations.yml"
        ]

    @pytest.mark.parametrize("wrong_id", ["1", "3"])
    def test_refuses_an_id_that_is_not_the_next_in_sequence(
        self, tmp_path: Path, wrong_id: str
    ) -> None:
        append_migration(tmp_path, _record("1"))

        with pytest.raises(ValueError, match="next id is 2"):
            append_migration(tmp_path, _record(wrong_id))

    def test_replaces_a_corrupted_file_with_only_the_new_record(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / ".boilerplate").mkdir()
        (tmp_path / MIGRATIONS_FILE).write_text("- id: [unclosed\n", encoding="utf-8")

        append_migration(tmp_path, _record("1"))

        assert [r.id for r in read_migrations(tmp_path)] == ["1"]


class TestNextMigrationId:
    """Ids run 1, 2, 3 and so on."""

    def test_is_one_for_an_empty_history(self) -> None:
        assert next_migration_id(()) == "1"

    def test_follows_the_last_record(self) -> None:
        assert next_migration_id((_record("1"), _record("2"))) == "3"
