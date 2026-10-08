"""The typed outcome of an update walk."""

import pytest
from pydantic import ValidationError

from boilerplate.composition.updating.update_outcome import UpdateOutcome
from boilerplate.composition.updating.update_status import UpdateStatus


class TestUpdateOutcome:
    def test_holds_what_the_walk_did(self) -> None:
        """Carry the layers updated and skipped, and the warnings."""
        outcome = UpdateOutcome(
            status=UpdateStatus.UPDATED,
            updated=("service",),
            skipped=("core",),
            warnings=("Layer 'x' drifted.",),
        )

        assert (outcome.updated, outcome.skipped, outcome.warnings) == (
            ("service",),
            ("core",),
            ("Layer 'x' drifted.",),
        )

    def test_a_paused_outcome_names_the_layer_and_its_conflicts(self) -> None:
        """Say where the walk stopped and which files conflicted."""
        outcome = UpdateOutcome(
            status=UpdateStatus.PAUSED,
            updated=("core", "service"),
            paused_at="service",
            conflicts=("README.md",),
        )

        assert (outcome.paused_at, outcome.conflicts) == ("service", ("README.md",))

    def test_a_pause_needs_the_layer_it_paused_at(self) -> None:
        """Refuse a paused outcome that names no layer."""
        with pytest.raises(ValidationError, match="paused_at"):
            UpdateOutcome(status=UpdateStatus.PAUSED, updated=("core",))

    @pytest.mark.parametrize("status", [UpdateStatus.UPDATED, UpdateStatus.UNDONE])
    def test_only_a_pause_names_a_layer(self, status: UpdateStatus) -> None:
        """Refuse ``paused_at`` on an outcome that did not pause."""
        with pytest.raises(ValidationError, match="paused_at"):
            UpdateOutcome(status=status, updated=("core",), paused_at="core")

    def test_is_immutable(self) -> None:
        """Freeze the outcome once built."""
        outcome = UpdateOutcome(status=UpdateStatus.UPDATED, updated=())

        with pytest.raises(ValidationError):
            outcome.status = UpdateStatus.UNDONE  # pyright: ignore[reportAttributeAccessIssue]
