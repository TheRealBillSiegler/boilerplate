"""The restore marker of design 02 §RestoreMarker: its fields and their combinations."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from boilerplate.models import (
    RestoreKind,
    RestoreMarker,
    RestoreOperation,
    RestorePhase,
)

STARTED = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)


def _fields(**overrides: object) -> dict[str, object]:
    return {
        "operation": "update",
        "kind": "complete",
        "phase": "copy_back",
        "start_commit": "a" * 40,
        "result_commit": "b" * 40,
        "targets": {"core": "1.1.0", "service": "1.2.0"},
        "started_at": STARTED.isoformat(),
        **overrides,
    }


class TestRestoreMarkerHappyPath:
    def test_parses_the_seven_fields_design_02_lists(self) -> None:
        """Read each field as design 02 §RestoreMarker types it."""
        marker = RestoreMarker.model_validate(_fields())

        assert (
            marker.operation,
            marker.kind,
            marker.phase,
            marker.start_commit,
            marker.result_commit,
            dict(marker.targets),
            marker.started_at,
        ) == (
            RestoreOperation.UPDATE,
            RestoreKind.COMPLETE,
            RestorePhase.COPY_BACK,
            "a" * 40,
            "b" * 40,
            {"core": "1.1.0", "service": "1.2.0"},
            STARTED,
        )

    def test_keeps_the_targets_in_walk_order(self) -> None:
        """Keep the order the walk ran the layers in, root last."""
        marker = RestoreMarker.model_validate_json(
            RestoreMarker.model_validate(_fields()).model_dump_json()
        )

        assert list(marker.targets) == ["core", "service"]

    def test_an_add_records_the_recording_phase(self) -> None:
        """Accept an add whose copy back has ended: it passes to ``recording``."""
        marker = RestoreMarker.model_validate(
            _fields(operation="add", phase="recording", targets={"docs": "1.0.0"})
        )

        assert (marker.operation, marker.phase) == (
            RestoreOperation.ADD,
            RestorePhase.RECORDING,
        )

    def test_at_phase_moves_only_the_phase(self) -> None:
        """Advance the phase as the run proceeds, every other field kept."""
        marker = RestoreMarker.model_validate(_fields())

        assert marker.at_phase(RestorePhase.TASKS) == RestoreMarker.model_validate(
            _fields(phase="tasks")
        )


class TestRestoreMarkerSadPath:
    @pytest.mark.parametrize(
        "overrides",
        [
            pytest.param({"operation": "adopt"}, id="operation-not-update-or-add"),
            pytest.param({"kind": "partial"}, id="unknown-kind"),
            pytest.param({"phase": "locking"}, id="unknown-phase"),
            pytest.param({"started_at": "2026-10-09T12:00:00"}, id="naive-start"),
            pytest.param({"operation": "add", "phase": "tasks"}, id="add-in-tasks"),
            pytest.param({"kind": "paused", "phase": "tasks"}, id="paused-in-tasks"),
        ],
    )
    def test_rejects_a_marker_design_02_does_not_allow(
        self, overrides: dict[str, object]
    ) -> None:
        """Refuse what design 02 rules out: an add and a paused run never run tasks."""
        with pytest.raises(ValidationError):
            RestoreMarker.model_validate(_fields(**overrides))
