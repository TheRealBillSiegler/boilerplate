"""Tests for the generated banner art's shape.

Expected values come from docs/design/05-cli-reference.md §Banner: widths 22 to
29 at 11 rows; two braces, ending on the cell row above the underscore's; each
bar exactly two dot rows tall in every column, with equal gaps; the long bars
ending in one column wherever the prompt leaves their end showing; a prompt of
one chevron, mirror-symmetric about its tip, and one underscore; no stray dots.
"""

from itertools import pairwise

import pytest

from boilerplate.cli.display.banner_art import LOGO_COLORS, LOGOS

WIDTHS = range(22, 30)
ROWS = 11
# Each braille dot's (column, row) within its 2 by 4 cell, and its bit.
_BITS = (
    (0, 0, 0x01),
    (0, 1, 0x02),
    (0, 2, 0x04),
    (1, 0, 0x08),
    (1, 1, 0x10),
    (1, 2, 0x20),
    (0, 3, 0x40),
    (1, 3, 0x80),
)

Dot = tuple[int, int]


def _dots(width: int) -> dict[Dot, str]:
    """Return every lit dot at ``width`` as (x, y) in dots, with its cell's mark."""
    dots: dict[Dot, str] = {}
    for row, (text, mask) in enumerate(
        zip(LOGOS[width], LOGO_COLORS[width], strict=True)
    ):
        for column, (char, mark) in enumerate(zip(text, mask, strict=True)):
            if mark == " ":
                continue
            for dx, dy, bit in _BITS:
                if (ord(char) - 0x2800) & bit:
                    dots[(column * 2 + dx, row * 4 + dy)] = mark
    return dots


def _clusters(dots: dict[Dot, str], mark: str) -> list[set[Dot]]:
    """Group the dots of one mark into clusters that touch, diagonals included."""
    left = {dot for dot, found in dots.items() if found == mark}
    clusters: list[set[Dot]] = []
    while left:
        frontier = [left.pop()]
        cluster = set(frontier)
        while frontier:
            x, y = frontier.pop()
            for near in ((x + i, y + j) for i in (-1, 0, 1) for j in (-1, 0, 1)):
                if near in left:
                    left.remove(near)
                    cluster.add(near)
                    frontier.append(near)
        clusters.append(cluster)
    return clusters


def _inside_bars(width: int) -> int:
    """Return a dot column inside every bar, left of the chevron: x=40 in the SVG."""
    return round(2 * width * 40 / 128)


def _bar_tops(dots: dict[Dot, str], width: int) -> list[int]:
    """Return each bar's top dot row, read down a column inside every bar."""
    lit = [(_inside_bars(width), y) in dots for y in range(ROWS * 4)]
    return [start for start, _ in _runs(lit)]


def _run_end(dots: dict[Dot, str], start: Dot, step: int) -> int:
    """Return the column where the blue run along a dot row from ``start`` ends."""
    x, y = start
    while dots.get((x + step, y)) == "b":
        x += step
    return x


def _bar_columns(dots: dict[Dot, str], width: int) -> range:
    """Return the dot columns from the bars' left end to the long bars' right end."""
    first = (_inside_bars(width), _bar_tops(dots, width)[0])
    return range(_run_end(dots, first, -1), _run_end(dots, first, 1) + 1)


def _span(cluster: set[Dot]) -> tuple[int, int]:
    """Return the top and bottom dot rows of ``cluster``."""
    rows = [y for _, y in cluster]
    return min(rows), max(rows)


def _is_bar_end(cluster: set[Dot], tops: list[int]) -> bool:
    """Return whether ``cluster`` is whole columns of one bar's two dot rows."""
    top = min(y for _, y in cluster)
    columns = {x for x, _ in cluster}
    return top in tops and cluster == {
        (x, top + row) for x in columns for row in (0, 1)
    }


def _runs(lit: list[bool]) -> list[tuple[int, int]]:
    """Return (start, length) of each run of lit entries."""
    runs: list[tuple[int, int]] = []
    start = None
    for index, on in enumerate([*lit, False]):
        if on and start is None:
            start = index
        elif not on and start is not None:
            runs.append((start, index - start))
            start = None
    return runs


class TestContract:
    def test_every_width_from_22_to_29_is_generated(self) -> None:
        assert sorted(LOGOS) == sorted(LOGO_COLORS) == list(WIDTHS)

    @pytest.mark.parametrize("width", WIDTHS)
    def test_each_width_is_11_rows_of_its_width(self, width: int) -> None:
        sizes = {
            (len(text), len(mask))
            for text, mask in zip(LOGOS[width], LOGO_COLORS[width], strict=True)
        }

        assert (len(LOGOS[width]), sizes) == (ROWS, {(width, width)})

    @pytest.mark.parametrize("width", WIDTHS)
    def test_a_cell_is_blank_exactly_where_its_mask_is(self, width: int) -> None:
        cells = {
            (char == " ", mark == " ")
            for text, mask in zip(LOGOS[width], LOGO_COLORS[width], strict=True)
            for char, mark in zip(text, mask, strict=True)
        }

        assert cells <= {(True, True), (False, False)}


class TestBraces:
    @pytest.mark.parametrize("width", WIDTHS)
    def test_two_braces_run_from_the_top_row_to_the_feet_row(self, width: int) -> None:
        """Each brace is one cluster, from the first cell row to the feet's."""
        feet_row = (ROWS - 2) * 4
        braces = [
            cluster
            for cluster in _clusters(_dots(width), "b")
            if _span(cluster)[0] < 4 and _span(cluster)[1] >= feet_row
        ]

        assert len(braces) == 2

    @pytest.mark.parametrize("width", WIDTHS)
    def test_no_blue_dot_on_the_underscores_cell_row(self, width: int) -> None:
        """05 §Banner: the braces end on the cell row above the underscore's."""
        rows = {y for (_, y), mark in _dots(width).items() if mark == "b"}

        assert max(rows) < (ROWS - 1) * 4


class TestBars:
    @pytest.mark.parametrize("width", WIDTHS)
    def test_eight_bars_two_dot_rows_tall(self, width: int) -> None:
        lit = [(_inside_bars(width), y) in _dots(width) for y in range(ROWS * 4)]

        assert [length for _, length in _runs(lit)] == [2] * 8

    @pytest.mark.parametrize("width", WIDTHS)
    def test_the_gaps_between_bars_are_equal(self, width: int) -> None:
        lit = [(_inside_bars(width), y) in _dots(width) for y in range(ROWS * 4)]
        runs = _runs(lit)

        assert len({b[0] - (a[0] + a[1]) for a, b in pairwise(runs)}) == 1

    @pytest.mark.parametrize("width", WIDTHS)
    def test_every_bar_column_lights_both_rows_or_neither(self, width: int) -> None:
        """A bar never thins to one dot row, at its ends or beside the prompt."""
        dots = _dots(width)
        halves = [
            (x, top)
            for top in _bar_tops(dots, width)
            for x in _bar_columns(dots, width)
            if (dots.get((x, top)) == "b") != (dots.get((x, top + 1)) == "b")
        ]

        assert halves == []

    @pytest.mark.parametrize("width", WIDTHS)
    def test_no_blue_dot_between_bars(self, width: int) -> None:
        """Between the braces, every blue dot lies on a bar's two rows."""
        dots = _dots(width)
        tops = _bar_tops(dots, width)
        between = [
            (x, y)
            for upper, lower in pairwise(tops)
            for y in range(upper + 2, lower)
            for x in _bar_columns(dots, width)
            if dots.get((x, y)) == "b"
        ]

        assert between == []

    @pytest.mark.parametrize("width", WIDTHS)
    def test_long_bars_end_in_one_column_unless_the_prompt_covers_it(
        self, width: int
    ) -> None:
        """The SVG draws the 1st, 3rd, 5th and 7th bars to the same x.

        The chevron passes over the 5th and 7th, and where it leaves a bar's
        end showing, as the logo does past the chevron's tip, the art shows it.
        """
        dots = _dots(width)
        tops = _bar_tops(dots, width)
        end = _bar_columns(dots, width)[-1]
        prompt_cells = {
            (x // 2, y // 4) for (x, y), mark in dots.items() if mark == "p"
        }
        missing = [
            y
            for top in tops[::2]
            for y in (top, top + 1)
            if (end // 2, y // 4) not in prompt_cells
            and (dots.get((end, y)), dots.get((end + 1, y))) != ("b", None)
        ]

        assert missing == []


class TestChevron:
    @pytest.mark.parametrize("width", WIDTHS)
    def test_the_prompt_is_a_chevron_and_an_underscore(self, width: int) -> None:
        assert len(_clusters(_dots(width), "p")) == 2

    @pytest.mark.parametrize("width", WIDTHS)
    def test_mirrors_about_its_tip(self, width: int) -> None:
        """The chevron is the prompt cluster above the underscore."""
        chevron = min(_clusters(_dots(width), "p"), key=_span)
        top, bottom = _span(chevron)

        assert {(x, top + bottom - y) for x, y in chevron} == chevron


class TestStrayDots:
    @pytest.mark.parametrize("width", WIDTHS)
    def test_the_prompt_has_no_cluster_of_four_dots_or_fewer(self, width: int) -> None:
        sizes = [len(cluster) for cluster in _clusters(_dots(width), "p")]

        assert min(sizes) > 4

    @pytest.mark.parametrize("width", WIDTHS)
    def test_a_blue_cluster_of_four_dots_or_fewer_is_a_bar_end(
        self, width: int
    ) -> None:
        """Only a bar's end showing past the prompt is that small."""
        dots = _dots(width)
        tops = _bar_tops(dots, width)
        strays = [
            cluster
            for cluster in _clusters(dots, "b")
            if len(cluster) <= 4 and not _is_bar_end(cluster, tops)
        ]

        assert strays == []
