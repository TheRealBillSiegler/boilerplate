"""The values an update step takes beyond the project's answers files."""

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StepInputs(BaseModel):
    """The values handed to one layer's update step.

    Attributes:
        supplied: Values the user supplies, such as ``--set`` and ``--answers``;
            data for the questions in the layer's scope.
        secrets: Secret answers given earlier in the same update; data for the
            questions in the layer's scope.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    supplied: Mapping[str, Any] = Field(default_factory=dict)
    secrets: Mapping[str, Any] = Field(default_factory=dict)
