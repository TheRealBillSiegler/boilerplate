"""What the post-walk task run executes."""

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TaskRun(BaseModel):
    """The tasks of a finished update and the secrets they may render.

    Attributes:
        tasks: The composition's accumulated tasks in Copier's shapes.
        secrets: Secret answers the walk asked, held in memory since no answers
            file records them.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    tasks: Sequence[Any] = ()
    secrets: Mapping[str, Any] = Field(default_factory=dict)
