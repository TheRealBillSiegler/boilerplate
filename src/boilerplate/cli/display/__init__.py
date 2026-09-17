"""Display package public API.

Exports:
- ColorMode from .color_mode
- DEFAULT_THEME, Display from .core
"""

from boilerplate.cli.display.color_mode import ColorMode
from boilerplate.cli.display.core import DEFAULT_THEME, Display

__all__ = [
    "DEFAULT_THEME",
    "ColorMode",
    "Display",
]
