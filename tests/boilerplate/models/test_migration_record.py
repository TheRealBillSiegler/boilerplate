"""Tests for the MigrationRecord model in migration_record.py."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from boilerplate.models import ChangeClassification, MigrationRecord, MigrationStatus

STAMP = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)


def _fields(**overrides: object) -> dict[str, object]:
    return {
        "id": "2",
        "from_version": "app@1.0.0",
        "to_version": "app@1.1.0",
        "timestamp": STAMP,
        "status": "success",
        "classification": "MINOR",
        **overrides,
    }


def _conflict(**overrides: object) -> dict[str, object]:
    return _fields(
        **{
            "status": "conflict",
            "targets": {"core": "2.0.0", "service": "1.0.0", "app": "1.1.0"},
            "finished": ["core", "service"],
            **overrides,
        }
    )


class TestMigrationRecordHappyPath:
    """A record names one operation and how it ended."""

    def test_parses_a_success_record(self) -> None:
        record = MigrationRecord.model_validate(_fields())

        assert record.status is MigrationStatus.SUCCESS
        assert record.classification is ChangeClassification.MINOR
        assert record.error is None
        assert record.targets is None
        assert record.finished is None

    def test_a_created_record_has_no_prior_state(self) -> None:
        record = MigrationRecord.model_validate(
            _fields(id="1", from_version=None, status="created", classification=None)
        )

        assert record.from_version is None
        assert record.classification is None

    def test_a_conflict_record_names_its_targets_and_finished_layers(self) -> None:
        record = MigrationRecord.model_validate(_conflict())

        assert record.targets == {"core": "2.0.0", "service": "1.0.0", "app": "1.1.0"}
        assert record.finished == ("core", "service")

    def test_serializes_status_and_classification_as_their_values(self) -> None:
        dumped = MigrationRecord.model_validate(_conflict()).model_dump(mode="json")

        assert dumped["status"] == "conflict"
        assert dumped["classification"] == "MINOR"
        assert dumped["finished"] == ["core", "service"]
        assert dumped["timestamp"] == "2026-10-08T12:00:00Z"


class TestMigrationRecordSadPath:
    """A record that breaks the schema's invariants is refused."""

    @pytest.mark.parametrize("record_id", ["", "0", "-1", "one", "1.5"])
    def test_rejects_an_id_that_is_not_a_positive_integer(self, record_id: str) -> None:
        with pytest.raises(ValidationError):
            MigrationRecord.model_validate(_fields(id=record_id))

    def test_rejects_an_unknown_status(self) -> None:
        with pytest.raises(ValidationError):
            MigrationRecord.model_validate(_fields(status="paused"))

    def test_rejects_a_naive_timestamp(self) -> None:
        with pytest.raises(ValidationError):
            MigrationRecord.model_validate(
                _fields(timestamp=datetime(2026, 10, 8, 12, 0))  # noqa: DTZ001
            )

    @pytest.mark.parametrize("field", ["targets", "finished"])
    def test_a_conflict_record_requires_the_resume_fields(self, field: str) -> None:
        fields = _conflict()
        del fields[field]

        with pytest.raises(ValidationError, match=field):
            MigrationRecord.model_validate(fields)

    @pytest.mark.parametrize(
        ("field", "value"), [("targets", {"core": "1.0.0"}), ("finished", ["core"])]
    )
    def test_only_a_conflict_record_carries_the_resume_fields(
        self, field: str, value: object
    ) -> None:
        with pytest.raises(ValidationError, match=field):
            MigrationRecord.model_validate(_fields(**{field: value}))

    def test_a_finished_layer_must_have_a_target(self) -> None:
        with pytest.raises(ValidationError, match="ghost"):
            MigrationRecord.model_validate(_conflict(finished=["core", "ghost"]))

    def test_rejects_a_target_that_is_not_pep_440(self) -> None:
        with pytest.raises(ValidationError, match="core"):
            MigrationRecord.model_validate(
                _conflict(
                    targets={"core": "latest", "service": "1.0.0", "app": "1.1.0"}
                )
            )

    def test_is_immutable(self) -> None:
        record = MigrationRecord.model_validate(_fields())

        with pytest.raises(ValidationError):
            record.status = MigrationStatus.FAILED
