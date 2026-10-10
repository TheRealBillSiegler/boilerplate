"""Tests for the banner's layout, width and colors.

Expected values come from docs/design/05-cli-reference.md §Banner: a 49 by 6
name, an 11-row logo 3 columns to its left, 25 columns wide at the default cell
shape, and a layout that fits in a terminal at least as tall as the layout plus
the blank line before it.
"""

import io
import re

import pytest
from rich.console import Console
from rich.text import Text

from boilerplate.cli.display.banner import build_banner, logo_width
from boilerplate.cli.display.banner_art import LOGO_COLORS
from boilerplate.cli.display.terminal_facts import TerminalFacts

# FIGlet's standard font, as `figlet boilerplate` prints it.
FIGLET_NAME = (
    " _           _ _                 _       _",
    "| |__   ___ (_) | ___ _ __ _ __ | | __ _| |_ ___",
    "| '_ \\ / _ \\| | |/ _ \\ '__| '_ \\| |/ _` | __/ _ \\",
    "| |_) | (_) | | |  __/ |  | |_) | | (_| | ||  __/",
    "|_.__/ \\___/|_|_|\\___|_|  | .__/|_|\\__,_|\\__\\___|",
    "                          |_|",
)
_BRAILLE = re.compile("[\u2800-\u28ff]")
# Brand blue, docs/design/05-cli-reference.md §Banner (#40B4E5).
_BRAND_BLUE = "#40b4e5"


def _facts(**changes: object) -> TerminalFacts:
    """Return a roomy terminal that can draw braille, with ``changes`` applied."""
    roomy: dict[str, object] = {
        "interactive": True,
        "columns": 120,
        "lines": 40,
        "braille": True,
        "ascii_only": False,
        "accessible": False,
        "opted_out": False,
        "cell_shape": None,
    }
    return TerminalFacts.model_validate(roomy | changes)


def _lines(banner: Text | None) -> list[str]:
    assert banner is not None
    return banner.plain.split("\n")


def _console(file: io.StringIO | None = None) -> Console:
    """Return a truecolor terminal console that ignores the host's NO_COLOR."""
    return Console(
        file=file,
        force_terminal=True,
        color_system="truecolor",
        no_color=False,
        width=200,
    )


def _ansi(banner: Text | None) -> str:
    assert banner is not None
    file = io.StringIO()
    _console(file).print(banner)
    return file.getvalue()


def _cell_colors(banner: Text | None) -> list[list[str | None]]:
    """Return each printed line's characters' foreground colors, as hex or None."""
    assert banner is not None
    return [
        [
            segment.style.color.triplet.hex
            if segment.style and segment.style.color and segment.style.color.triplet
            else None
            for segment in line
            for _ in segment.text
        ]
        for line in _console().render_lines(banner, pad=False)
    ]


class TestLogoBesideName:
    def test_is_eleven_rows_tall(self) -> None:
        assert len(_lines(build_banner(_facts()))) == 11

    def test_is_77_columns_wide_at_the_default_cell_shape(self) -> None:
        assert max(len(line) for line in _lines(build_banner(_facts()))) == 25 + 3 + 49

    def test_sets_the_name_three_columns_right_of_the_logo(self) -> None:
        lines = _lines(build_banner(_facts()))

        assert tuple(line[28:] for line in lines if len(line) > 25) == FIGLET_NAME

    def test_centers_the_name_vertically(self) -> None:
        lines = _lines(build_banner(_facts()))
        name_rows = [index for index, line in enumerate(lines) if len(line) > 25]

        above, below = name_rows[0], len(lines) - 1 - name_rows[-1]
        assert abs(above - below) <= 1

    def test_draws_the_logo_in_braille(self) -> None:
        assert _BRAILLE.search(_lines(build_banner(_facts()))[0])

    def test_fits_exactly_77_by_12(self) -> None:
        """11 rows and the blank line before them."""
        assert len(_lines(build_banner(_facts(columns=77, lines=12)))) == 11


class TestNameAlone:
    @pytest.mark.parametrize(
        "changes",
        [
            pytest.param({"columns": 76}, id="one-column-short-of-the-logo"),
            pytest.param({"lines": 11}, id="one-line-short-of-the-logo"),
            pytest.param({"columns": 49, "lines": 7}, id="exactly-49-by-7"),
            pytest.param({"ascii_only": True}, id="ascii-only"),
            pytest.param({"braille": False}, id="no-braille"),
        ],
    )
    def test_prints_the_figlet_name_without_the_logo(
        self, changes: dict[str, object]
    ) -> None:
        assert tuple(_lines(build_banner(_facts(**changes)))) == FIGLET_NAME


class TestNoBanner:
    @pytest.mark.parametrize(
        "changes",
        [
            pytest.param({"columns": 48}, id="narrower-than-the-name"),
            pytest.param({"lines": 6}, id="one-line-short-of-the-name"),
            pytest.param({"interactive": False}, id="not-a-terminal"),
            pytest.param({"accessible": True}, id="accessible"),
            pytest.param({"opted_out": True}, id="opted-out"),
        ],
    )
    def test_nothing_prints(self, changes: dict[str, object]) -> None:
        assert build_banner(_facts(**changes)) is None


class TestLogoWidth:
    @pytest.mark.parametrize(
        ("cell_shape", "columns"),
        [
            pytest.param(None, 25, id="unknown-takes-the-default-2.25"),
            pytest.param(2.25, 25, id="2.25"),
            pytest.param(2.0, 22, id="2.0"),
            pytest.param(2.1, 23, id="2.1"),
            pytest.param(2.55, 28, id="2.55"),
            pytest.param(2.6, 29, id="2.6"),
            pytest.param(1.5, 22, id="below-the-range"),
            pytest.param(3.0, 29, id="above-the-range"),
        ],
    )
    def test_is_the_generated_width_nearest_eleven_times_the_shape(
        self, cell_shape: float | None, columns: int
    ) -> None:
        assert logo_width(cell_shape) == columns

    def test_a_reported_cell_shape_sets_the_printed_width(self) -> None:
        lines = _lines(build_banner(_facts(cell_shape=2.0)))

        assert max(len(line) for line in lines) == 22 + 3 + 49

    @pytest.mark.parametrize(
        ("cell_shape", "columns", "rows"),
        [
            pytest.param(2.0, 74, 11, id="22-column-logo-fits-74"),
            pytest.param(2.0, 73, 6, id="22-column-logo-not-73"),
            pytest.param(2.6, 81, 11, id="29-column-logo-fits-81"),
            pytest.param(2.6, 80, 6, id="29-column-logo-not-80"),
        ],
    )
    def test_the_logo_layout_needs_its_own_width_plus_52_columns(
        self, cell_shape: float, columns: int, rows: int
    ) -> None:
        banner = build_banner(_facts(cell_shape=cell_shape, columns=columns))

        assert len(_lines(banner)) == rows


class TestColors:
    def test_blue_cells_print_brand_blue_and_prompt_cells_the_default_color(
        self,
    ) -> None:
        """The prompt keeps the terminal's default color, so it follows the theme."""
        colors = _cell_colors(build_banner(_facts()))
        printed = [(row + [None] * 25)[:25] for row in colors]

        assert printed == [
            [_BRAND_BLUE if mark == "b" else None for mark in mask]
            for mask in LOGO_COLORS[25]
        ]

    def test_the_name_is_bold(self) -> None:
        output = _ansi(build_banner(_facts(ascii_only=True)))

        assert f"\x1b[1m{FIGLET_NAME[1]}" in output
