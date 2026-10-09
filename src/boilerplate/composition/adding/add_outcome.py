"""What an add did."""

from pydantic import BaseModel, ConfigDict

from boilerplate.composition.adding.add_status import AddStatus


class AddOutcome(BaseModel):
    """The typed result of an add.

    Attributes:
        status: How the add ended.
        layer: The layer that was added, or that the add undone had been adding.
        version: The version the layer was added at.
        warnings: What the add found and went on from: ignored files the layer
            wrote, which the copy back does not carry.
        ignored_left: The ignored files and folders a task made that the undo
            of the add left in place; empty unless the add was undone. A change
            inside an ignored folder that already existed is not seen.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: AddStatus
    layer: str
    version: str
    warnings: tuple[str, ...] = ()
    ignored_left: tuple[str, ...] = ()
