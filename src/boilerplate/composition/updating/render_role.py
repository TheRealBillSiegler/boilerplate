"""Tell which render of Copier's update a destination directory belongs to."""

from enum import StrEnum
from pathlib import Path

from boilerplate.integrations.copier_types import (
    NEW_COPY_DIR_PREFIX,
    OLD_COPY_DIR_PREFIX,
)


class RenderRole(StrEnum):
    """The three renders one Copier update makes.

    Attributes:
        OLD_COPY: The project as the recorded release produced it.
        IN_PLACE: The project itself, re-rendered at the target release.
        NEW_COPY: A clean render at the target release, to diff against the
            old copy.
    """

    OLD_COPY = "old_copy"
    IN_PLACE = "in_place"
    NEW_COPY = "new_copy"


def render_role(destination: Path) -> RenderRole:
    """Return the render that writes into `destination`.

    Copier renders the old and new copies into temporary directories whose
    names start with fixed prefixes, and renders in place into the project.

    Args:
        destination: The destination directory of the render.

    Returns:
        The role of the render.

    Examples:
        >>> from pathlib import Path
        >>> render_role(Path("project"))
        <RenderRole.IN_PLACE: 'in_place'>
        >>> render_role(Path("tmp") / f"{OLD_COPY_DIR_PREFIX}ab12")
        <RenderRole.OLD_COPY: 'old_copy'>
    """
    for part in destination.parts:
        if part.startswith(OLD_COPY_DIR_PREFIX):
            return RenderRole.OLD_COPY
        if part.startswith(NEW_COPY_DIR_PREFIX):
            return RenderRole.NEW_COPY
    return RenderRole.IN_PLACE
