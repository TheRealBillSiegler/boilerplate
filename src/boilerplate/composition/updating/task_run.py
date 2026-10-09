"""What the task run after an update's walk or an add executes."""

from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class TaskRun(BaseModel):
    """The tasks of a finished update or add, how they run, and their secrets.

    Attributes:
        operation: The Copier operation the tasks run under: ``update`` after
            an update, ``copy`` after an add, as at compose.
        tasks: The tasks in Copier's shapes: the composition's accumulated
            tasks after an update, the added layer's own after an add.
        secrets: Secret answers the run asked, held in memory since no answers
            file records them.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    operation: Literal["copy", "update"]
    tasks: Sequence[Any] = ()
    secrets: Mapping[str, Any] = Field(default_factory=dict)
