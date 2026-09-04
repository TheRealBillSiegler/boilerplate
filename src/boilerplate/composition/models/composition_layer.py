"""Single composition layer model."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from boilerplate.composition.models.json_types import JSON


class CompositionLayer(BaseModel):
    """One layer's contribution and its effect."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    version: str
    path: Path
    values: dict[str, JSON]
    state_after: dict[str, JSON] | None = None
    delta: dict[str, JSON] | None = None

    @property
    def state(self) -> dict[str, JSON]:
        """Normalized state mapping after this layer is applied."""
        return self.state_after or {}

    @property
    def delta_view(self) -> dict[str, JSON]:
        """Normalized delta mapping describing this layer's changes."""
        return self.delta or {}
