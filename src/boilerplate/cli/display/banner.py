"""Choose and color the banner: the braille logo beside the name.

The art comes from ``banner_art``, which scripts/render_cli_banner.py generates
from the CLI logo. This module picks the layout that fits the terminal and gives
it the banner's colors; it reads nothing itself, so every decision follows from
the ``TerminalFacts`` it is given.
"""
# Spec: docs/design/05-cli-reference.md §Banner

from itertools import groupby
from typing import Final

from rich.style import Style
from rich.text import Text

from boilerplate.cli.display.banner_art import LOGO_COLORS, LOGOS, NAME
from boilerplate.cli.display.terminal_facts import TerminalFacts

BRAND_BLUE: Final = "#40b4e5"
# Cell height divided by cell width when the terminal reports none. Common
# terminal fonts give shapes from about 2.0 to 2.57; 2.25 falls inside that
# range and gives 25 columns, the middle of the generated widths.
DEFAULT_CELL_SHAPE: Final = 2.25
# Columns between the logo and the name.
GAP: Final = 3

_LOGO_ROWS: Final = len(next(iter(LOGOS.values())))
_NAME_WIDTH: Final = max(len(row) for row in NAME)
_STYLES: Final[dict[str, Style | None]] = {
    "b": Style(color=BRAND_BLUE),
    "p": None,  # the prompt keeps the terminal's default text color
    " ": None,
}


def logo_width(cell_shape: float | None) -> int:
    """Return the logo width, in columns, that keeps the logo square.

    Args:
        cell_shape: Cell height divided by cell width, or ``None`` when the
            terminal does not report it.

    Returns:
        The generated width nearest to the logo's rows times the cell shape.

    Examples:
        >>> logo_width(None)
        25
        >>> logo_width(2.0)
        22
    """
    shape = DEFAULT_CELL_SHAPE if cell_shape is None else cell_shape
    return min(LOGOS, key=lambda width: abs(width - _LOGO_ROWS * shape))


def build_banner(facts: TerminalFacts) -> Text | None:
    """Return the banner that fits the terminal, or ``None`` when none may print.

    Args:
        facts: What the terminal is and allows.

    Returns:
        The logo beside the name when the terminal can draw braille and has
        room for both; else the name alone when it has room for that; else
        ``None``. Nothing prints on a terminal that is not interactive, under
        accessibility, or once opted out.
    """
    if not facts.interactive or facts.accessible or facts.opted_out:
        return None
    if facts.braille and not facts.ascii_only:
        width = logo_width(facts.cell_shape)
        if _fits(facts, width + GAP + _NAME_WIDTH, _LOGO_ROWS):
            return _logo_beside_name(width)
    if _fits(facts, _NAME_WIDTH, len(NAME)):
        return Text("\n").join(Text(row, style="bold") for row in NAME)
    return None


def _fits(facts: TerminalFacts, width: int, height: int) -> bool:
    """Return True when a layout fits the terminal.

    It fits when the terminal is at least as wide as the layout, so no row
    wraps, and tall enough for the layout and the blank line before it, so the
    whole banner can be on screen at once. More height buys nothing: the help
    that follows scrolls the banner away regardless.
    """
    return facts.columns >= width and facts.lines >= height + 1


def _logo_beside_name(width: int) -> Text:
    """Return the logo at ``width`` with the name centered to its right."""
    top = (_LOGO_ROWS - len(NAME)) // 2
    lines: list[Text] = []
    for index, (row, mask) in enumerate(
        zip(LOGOS[width], LOGO_COLORS[width], strict=True)
    ):
        line = Text()
        for mark, run in groupby(zip(row, mask, strict=True), key=lambda cell: cell[1]):
            line.append("".join(char for char, _ in run), style=_STYLES[mark])
        if 0 <= index - top < len(NAME):
            line.append(" " * GAP)
            line.append(NAME[index - top], style="bold")
        line.rstrip()
        lines.append(line)
    return Text("\n").join(lines)
