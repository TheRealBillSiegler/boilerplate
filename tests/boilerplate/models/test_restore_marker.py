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

    def test_an_add_records_the_tasks_phase(self) -> None:
        """Accept an add whose tasks run: design 02 gives it the update's phases."""
        marker = RestoreMarker.model_validate(
            _fields(operation="add", phase="tasks", targets={"docs": "1.0.0"})
        )

        assert (marker.operation, marker.phase) == (
            RestoreOperation.ADD,
            RestorePhase.TASKS,
        )

    def test_an_add_records_the_recording_phase(self) -> None:
        """Accept an add whose copy back has ended: it passes to ``recording``."""
        marker = RestoreMarker.model_validate(
            _fields(operation="add", phase="recording", targets={"docs": "1.0.0"})
        )

        assert (marker.operation, marker.phase) == (
            RestoreOperation.ADD,
            RestorePhase.RECORDING,
        )

    def test_a_paused_run_keeps_its_finished_layers_and_the_paused_one(self) -> None:
        """Read ``finished`` and ``paused_layer`` as design 02 §RestoreMarker types."""
        marker = RestoreMarker.model_validate(
            _fields(
                kind="paused",
                phase="recording",
                targets={"core": "1.1.0", "service": "1.2.0", "app": "1.1.0"},
                finished=["core"],
                paused_layer="service",
            )
        )

        assert (marker.finished, marker.paused_layer) == (("core",), "service")

    def test_a_complete_run_has_no_finished_layers_and_no_paused_one(self) -> None:
        """Leave ``finished`` empty and ``paused_layer`` absent, as design 02 says."""
        marker = RestoreMarker.model_validate(_fields())

        assert (marker.finished, marker.paused_layer) == ((), None)

    def test_accepts_a_sha256_repository_commit(self) -> None:
        """Accept the 64-digit object id of a SHA-256 repository as well as SHA-1's."""
        marker = RestoreMarker.model_validate(
            _fields(start_commit="c" * 64, result_commit="d" * 64)
        )

        assert (marker.start_commit, marker.result_commit) == ("c" * 64, "d" * 64)

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
            pytest.param({"kind": "paused", "phase": "tasks"}, id="paused-in-tasks"),
        ],
    )
    def test_rejects_a_marker_design_02_does_not_allow(
        self, overrides: dict[str, object]
    ) -> None:
        """Refuse what design 02 rules out: a paused run never runs tasks."""
        with pytest.raises(ValidationError):
            RestoreMarker.model_validate(_fields(**overrides))

    @pytest.mark.parametrize(
        "overrides",
        [
            pytest.param({"start_commit": "--output=x"}, id="start-is-an-option"),
            pytest.param({"result_commit": "HEAD"}, id="result-is-a-ref-name"),
            pytest.param({"start_commit": "a" * 12}, id="start-abbreviated"),
            pytest.param({"result_commit": "A" * 40}, id="result-upper-case"),
            pytest.param({"targets": {}}, id="no-targets"),
            pytest.param(
                {"operation": "add", "phase": "recording"}, id="add-with-two-targets"
            ),
            pytest.param({"kind": "paused"}, id="paused-without-its-layer"),
            pytest.param({"finished": ["core"]}, id="complete-with-finished"),
            pytest.param({"paused_layer": "core"}, id="complete-with-paused-layer"),
            pytest.param(
                {"kind": "paused", "paused_layer": "docs"},
                id="paused-layer-not-a-target",
            ),
            pytest.param(
                {"kind": "paused", "finished": ["docs"], "paused_layer": "service"},
                id="finished-layer-not-a-target",
            ),
            pytest.param(
                {"kind": "paused", "finished": ["service"], "paused_layer": "service"},
                id="paused-layer-among-finished",
            ),
        ],
    )
    def test_rejects_a_marker_no_run_writes(self, overrides: dict[str, object]) -> None:
        """Refuse a marker read back from disk that no run could have written.

        A run records full object ids from ``git rev-parse``, at least the one
        layer it walked, and for an add exactly the one layer it adds; the
        commits go into git's argv, so anything else is refused at the boundary.
        A paused run names the layer that paused and the layers it finished
        before it, all of them layers of the walk; a complete run names neither.
        """
        with pytest.raises(ValidationError):
            RestoreMarker.model_validate(_fields(**overrides))
