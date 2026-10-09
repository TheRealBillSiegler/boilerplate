"""The state of an update or add that is copying its result back."""
# Spec: docs/design/02-data-models.md §RestoreMarker

from collections.abc import Mapping
from typing import Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, model_validator

from boilerplate.models.restore_kind import RestoreKind
from boilerplate.models.restore_operation import RestoreOperation
from boilerplate.models.restore_phase import RestorePhase

__all__ = ["RestoreMarker"]


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
        start_commit: The commit HEAD pointed at when the run began.
        result_commit: The staging worktree's last per-layer commit, the start
            commit when no layer finished.
        targets: Each layer of the walk, in walk order, with the version the
            walk was moving it to.
        started_at: When the run began.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    operation: RestoreOperation
    kind: RestoreKind
    phase: RestorePhase
    start_commit: str
    result_commit: str
    targets: Mapping[str, str]
    started_at: AwareDatetime

    @model_validator(mode="after")
    def _check_tasks_phase(self) -> Self:
        """Allow the ``tasks`` phase only on a complete update.

        An add runs its tasks after its record, and a paused update runs none.

        Returns:
            The validated marker.

        Raises:
            ValueError: If an add or a paused run is in the ``tasks`` phase.
        """
        if self.phase is RestorePhase.TASKS and (
            self.operation is not RestoreOperation.UPDATE
            or self.kind is not RestoreKind.COMPLETE
        ):
            raise ValueError("only a complete update runs its tasks under the marker")
        return self

    def at_phase(self, phase: RestorePhase) -> Self:
        """Return this marker moved on to `phase`.

        Args:
            phase: The step the run has reached.

        Returns:
            A copy with `phase`, checked as a new marker is.

        Raises:
            pydantic.ValidationError: If `phase` is ``tasks`` for an add or a
                paused run.
        """
        return self.model_validate({**self.model_dump(), "phase": phase})
