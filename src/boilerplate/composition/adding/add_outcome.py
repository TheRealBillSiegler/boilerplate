"""What an add did."""

from pydantic import BaseModel, ConfigDict

from boilerplate.composition.adding.add_status import AddStatus


class AddOutcome(BaseModel):
    """The typed result of an add.

    Attributes:
        status: How the add ended.
        layer: The layer that was added, or that the add undone had been adding.
        version: The version the layer was added at.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: AddStatus
    layer: str
    version: str
