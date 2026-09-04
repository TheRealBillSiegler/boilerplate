"""Models for template execution context and configuration."""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ExecutionContext(BaseModel):
    """Context for template execution containing all execution parameters.

    This model encapsulates the parameters needed for template rendering,
    including destination path, user context data, and execution flags.
    """

    destination: Path = Field(
        description="Target directory where the template will be rendered"
    )
    context_data: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Forced answers: values supplied here are taken as-is and are not "
            "prompted (Copier's ``data`` channel). Used for answers threaded "
            "between composition layers."
        ),
    )
    profile: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Overridable default answers (the profile, from profile.toml). "
            "They pre-fill interactive prompts and are taken as-is when "
            "non-interactive, but an interactive answer or a forced "
            "``context_data`` value overrides them (Copier's ``user_defaults`` "
            "channel)."
        ),
    )
    overwrite: bool = Field(
        default=False, description="Whether to overwrite existing files at destination"
    )
    interactive: bool = Field(
        default=True, description="Whether to prompt user for template questions"
    )
    skip_tasks: bool = Field(
        default=False,
        description=(
            "Whether to skip task execution on the final layer. Non-final "
            "layers always skip tasks regardless of this flag."
        ),
    )


__all__ = [
    "ExecutionContext",
]
