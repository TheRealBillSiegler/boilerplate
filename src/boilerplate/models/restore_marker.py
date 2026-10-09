"""The state of an update or add that is copying its result back."""
# Spec: docs/design/02-data-models.md §RestoreMarker

from collections.abc import Mapping
from typing import Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from boilerplate.models.restore_kind import RestoreKind
from boilerplate.models.restore_operation import RestoreOperation
from boilerplate.models.restore_phase import RestorePhase

__all__ = ["RestoreMarker"]

_OBJECT_ID_PATTERN = r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$"
"""A full git object id: 40 hex digits for SHA-1, 64 for SHA-256."""


class RestoreMarker(BaseModel):
    """What a run cut off between its copy back and its record needs to be finished.

    The marker is written before the copy back changes a file and removed after
    the run appends its record, so a marker found when a command starts belongs
    to a run that was cut off in between. It lives in the git directory, apart
    from the staging folder that the stale cleanup removes.

    Attributes:
        operation: The command the run belongs to.
        kind: Whether the walk finished every layer or a conflict paused it.
        phase: How far the run got after its walk.
        start_commit: The commit HEAD pointed at when the run began, a full
            object id.
        result_commit: The staging worktree's last per-layer commit, the start
            commit when no layer finished; a full object id.
        targets: Each layer of the walk, in walk order, with the version the
            walk was moving it to; never empty, and one layer for an add.
        finished: The layers whose steps a paused walk finished, in walk
            order, the paused layer excluded; empty for a complete run.
        paused_layer: The layer whose merge left conflict markers, which
            follows the finished layers; ``None`` for a complete run.
        started_at: When the run began.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    operation: RestoreOperation
    kind: RestoreKind
    phase: RestorePhase
    start_commit: str = Field(pattern=_OBJECT_ID_PATTERN)
    result_commit: str = Field(pattern=_OBJECT_ID_PATTERN)
    targets: Mapping[str, str]
    finished: tuple[str, ...] = ()
    paused_layer: str | None = None
    started_at: AwareDatetime

    @model_validator(mode="after")
    def _check_tasks_phase(self) -> Self:
        """Allow the ``tasks`` phase only on a complete run.

        An update and an add run their tasks before their lock and their
        record, and a paused update runs none.

        Returns:
            The validated marker.

        Raises:
            ValueError: If a paused run is in the ``tasks`` phase.
        """
        if self.phase is RestorePhase.TASKS and self.kind is not RestoreKind.COMPLETE:
            raise ValueError("only a complete run runs its tasks under the marker")
        return self

    @model_validator(mode="after")
    def _check_targets(self) -> Self:
        """Require at least one target, and exactly one for an add.

        A walk moves at least one layer, and an add walks only the layer it adds.

        Returns:
            The validated marker.

        Raises:
            ValueError: If `targets` is empty, or an add names other than one.
        """
        if not self.targets:
            raise ValueError("a restore marker names at least one target")
        if self.operation is RestoreOperation.ADD and len(self.targets) != 1:
            raise ValueError("an add's restore marker names exactly one target")
        return self

    @model_validator(mode="after")
    def _check_paused_layers(self) -> Self:
        """Require the paused walk's layers on a paused run, and only there.

        A conflict pauses the walk at one of its layers, after the layers it
        finished; a complete run finished every layer and paused at none.

        Returns:
            The validated marker.

        Raises:
            ValueError: If a paused run names no paused layer, a complete run
                names finished or paused layers, or a named layer is not one
                of the walk's or is both finished and paused.
        """
        if self.kind is RestoreKind.COMPLETE:
            if self.finished or self.paused_layer is not None:
                raise ValueError("a complete run names no finished or paused layer")
            return self
        if self.paused_layer is None:
            raise ValueError("a paused run names the layer that paused it")
        named = (*self.finished, self.paused_layer)
        if not set(named) <= set(self.targets):
            raise ValueError("a paused run names only layers of its walk")
        if self.paused_layer in self.finished:
            raise ValueError("the paused layer is not among the finished layers")
        return self

    def at_phase(self, phase: RestorePhase) -> Self:
        """Return this marker moved on to `phase`.

        Args:
            phase: The step the run has reached.

        Returns:
            A copy with `phase`, checked as a new marker is.

        Raises:
            pydantic.ValidationError: If `phase` is ``tasks`` for a paused run.
        """
        return self.model_validate({**self.model_dump(), "phase": phase})
