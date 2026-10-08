"""The intent journal records a staged operation's phase for crash recovery."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from boilerplate.composition.staging import (
    JOURNAL_NAME,
    IntentJournal,
    IntentOperation,
)

STARTED = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


def journal(**changes: object) -> IntentJournal:
    fields: dict[str, object] = {
        "operation": IntentOperation.UPDATE,
        "phase": "staging",
        "started_at": STARTED,
        "staging_dir": "/tmp/unique",
        "destination": "/work/project",
        "template_ref": None,
    }
    return IntentJournal.model_validate(fields | changes)


class TestWriteAndRead:
    def test_round_trips_through_the_file(self, tmp_path: Path) -> None:
        written = journal(template_ref="core@3.0.0")

        written.write(tmp_path)

        assert IntentJournal.read(tmp_path) == written

    def test_file_has_the_designed_name(self, tmp_path: Path) -> None:
        journal().write(tmp_path)

        assert (tmp_path / JOURNAL_NAME).name == ".boilerplate-commit-intent.json"
        assert (tmp_path / JOURNAL_NAME).is_file()

    def test_write_leaves_no_temporary_file(self, tmp_path: Path) -> None:
        journal().write(tmp_path)

        assert [p.name for p in tmp_path.iterdir()] == [JOURNAL_NAME]

    def test_rewrite_replaces_the_phase(self, tmp_path: Path) -> None:
        journal().write(tmp_path)

        journal(phase="committing").write(tmp_path)

        assert IntentJournal.read(tmp_path).phase == "committing"

    def test_unparseable_file_raises(self, tmp_path: Path) -> None:
        (tmp_path / JOURNAL_NAME).write_text("{not json", encoding="utf-8")

        with pytest.raises(ValidationError):
            IntentJournal.read(tmp_path)


class TestOperation:
    @pytest.mark.parametrize("name", ["create", "update", "add", "adopt", "env_apply"])
    def test_designed_operations_are_accepted(self, name: str) -> None:
        assert journal(operation=name).operation == IntentOperation(name)

    def test_unknown_operation_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            journal(operation="eject")
