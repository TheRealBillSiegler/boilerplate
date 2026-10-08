"""What the user asks of one add."""

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AddRequest(BaseModel):
    """The choices that shape one add.

    Attributes:
        name: The template to add, as its ``boilerplate.yml`` names it.
        source: The template's git-backed source, a local path or a URL.
        ref: The tag, ``git describe`` string or commit to add; ``None`` adds the
            latest release.
        supplied: Values the user supplies, such as ``--set`` and ``--answers``;
            data for the questions of the layer and its ancestors.
        interactive: Whether the copy prompts for the layer's own questions;
            otherwise each takes its default or a supplied value.
        no_tasks: Whether to skip the layer's tasks after the copy back.
        quiet: Whether to silence Copier's progress output.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    source: str
    ref: str | None = None
    supplied: Mapping[str, Any] = Field(default_factory=dict)
    interactive: bool = False
    no_tasks: bool = False
    quiet: bool = True
