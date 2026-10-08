"""The migration record an add appends to the project's log."""

from pathlib import Path

from boilerplate.composition.adding.add_recorder import AddRecorder
from boilerplate.models import MigrationStatus
from boilerplate.project_state.migrations_file import read_migrations


class TestSuccess:
    def test_records_the_added_layer_with_no_prior_version_or_classification(
        self, tmp_path: Path
    ) -> None:
        """Follow design 02: ``from_version`` and ``classification`` are null."""
        AddRecorder(tmp_path).success("docs@1.0.0")

        (record,) = read_migrations(tmp_path)
        assert (
            record.status,
            record.from_version,
            record.to_version,
            record.classification,
            record.error,
        ) == (MigrationStatus.SUCCESS, None, "docs@1.0.0", None, None)

    def test_numbers_the_record_after_those_already_in_the_log(
        self, tmp_path: Path
    ) -> None:
        """Continue the sequence of the log."""
        recorder = AddRecorder(tmp_path)
        recorder.success("docs@1.0.0")

        recorder.success("ci@1.0.0")

        assert [r.id for r in read_migrations(tmp_path)] == ["1", "2"]


class TestFailed:
    def test_records_why_the_add_is_marked_failed(self, tmp_path: Path) -> None:
        """Keep the task failure the add finished with."""
        AddRecorder(tmp_path).failed("docs@1.0.0", "task failed")

        (record,) = read_migrations(tmp_path)
        assert (record.status, record.to_version, record.error) == (
            MigrationStatus.FAILED,
            "docs@1.0.0",
            "task failed",
        )
