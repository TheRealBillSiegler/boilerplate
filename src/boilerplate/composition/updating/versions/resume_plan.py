"""How a paused update continues."""
# Spec: docs/design/04-composition-engine.md §Safe Update

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict

from boilerplate.types.serializable_version import SerializableVersion

__all__ = ["ResumePlan"]


class ResumePlan(BaseModel):
    """What a pending ``conflict`` record says the resumed walk does.

    Attributes:
        finished: The layers the paused walk completed, in walk order; the
            resumed walk skips them.
        remaining: The layers the resumed walk runs, in the lock's order.
        targets: The version every layer was being updated to when the walk
            paused, in the lock's order; the resumed walk uses these, never
            the latest release.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    finished: tuple[str, ...]
    remaining: tuple[str, ...]
    targets: Mapping[str, SerializableVersion]
