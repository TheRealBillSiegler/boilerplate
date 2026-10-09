"""What an update walk did."""

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from boilerplate.composition.updating.update_status import UpdateStatus


class UpdateOutcome(BaseModel):
    """The typed result of an update walk.

    Attributes:
        status: How the walk ended.
        updated: The layers the walk ran, in walk order; on a pause, the layer
            that paused is the last of them.
        skipped: The layers a resumed walk skipped because the paused walk had
            finished them.
        paused_at: The layer whose update left conflicts; set on a pause only.
        conflicts: The conflicted paths of the paused layer, as git lists them.
        warnings: What the walk found and went on from: layers that disagree with
            the lock, answers files edited since the lock, a different Copier.
        ignored_left: The ignored files and folders a task made that the undo
            of the update left in place; empty unless the update was undone. A
            change inside an ignored folder that already existed is not seen.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: UpdateStatus
    updated: tuple[str, ...]
    skipped: tuple[str, ...] = ()
    paused_at: str | None = None
    conflicts: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    ignored_left: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _check_pause(self) -> Self:
        """Require ``paused_at`` on a pause and only there.

        Returns:
            The validated outcome.

        Raises:
            ValueError: If a paused outcome names no layer, or another outcome
                names one.
        """
        if (self.status is UpdateStatus.PAUSED) != (self.paused_at is not None):
            raise ValueError("paused_at is set when the walk paused, and only then")
        return self
