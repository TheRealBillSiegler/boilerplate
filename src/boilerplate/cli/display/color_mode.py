"""The color modes a user can select with ``--color``."""

from enum import StrEnum


class ColorMode(StrEnum):
    """Color output mode selected by the global ``--color`` option.

    Follows the convention git, cargo, and ripgrep established
    (docs/design/05-cli-reference.md §Global Options).

    Attributes:
        AUTO: Color only when stdout is a terminal, and never when
            ``NO_COLOR`` or ``BOILERPLATE_ACCESSIBLE`` is set.
        ALWAYS: Force color on, even when piped.
        NEVER: Force color off.
    """

    AUTO = "auto"
    ALWAYS = "always"
    NEVER = "never"
