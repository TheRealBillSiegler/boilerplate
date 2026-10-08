"""What the user asks of one update."""

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class UpdateRequest(BaseModel):
    """The choices that shape one update walk.

    Attributes:
        targets: Explicit target refs keyed by layer, as ``--target-version``
            names them; a layer not named moves to its latest release. A paused
            walk's recorded targets bind, and a ref that differs from them is
            refused.
        supplied: Values the user supplies, such as ``--set`` and ``--answers``;
            data for the questions of every layer whose scope holds them.
        interactive: Whether each layer's step prompts for its questions, with
            the recorded answer as the default.
        skip_answered: Whether a step asks only the questions no answers file
            records.
        no_tasks: Whether to skip the composition's tasks after the walk.
        quiet: Whether to silence Copier's progress output.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    targets: Mapping[str, str] = Field(default_factory=dict)
    supplied: Mapping[str, Any] = Field(default_factory=dict)
    interactive: bool = False
    skip_answered: bool = False
    no_tasks: bool = False
    quiet: bool = True
