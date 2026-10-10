"""Tests for scripts/render_cli_banner.py.

The script is not package code, so it is loaded from its path. The shape rules
the generated art must meet are tested on the art itself, in
tests/boilerplate/cli/display/test_banner_art.py; these tests cover the steps
that get it there: reading the SVG's paths, keeping the braces' feet above the
underscore, lighting the bars a whole column at a time, the one-color-per-cell
rule, and writing the art module. They also check that the committed art
matches a fresh render, and the script's command line.
"""

import importlib.util
import re
from pathlib import Path

import numpy as np
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "scripts" / "render_cli_banner.py"
_LOGO = _REPO_ROOT / "docs" / "assets" / "boilerplate-cli-logo.svg"
_ART = _REPO_ROOT / "src" / "boilerplate" / "cli" / "display" / "banner_art.py"
_SPEC = importlib.util.spec_from_file_location("render_cli_banner", _MODULE_PATH)
assert _SPEC is not None
assert _SPEC.loader is not None
render_cli_banner = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(render_cli_banner)


class TestSubpaths:
    def test_lines_and_a_close_make_one_polygon(self) -> None:
        assert render_cli_banner.subpaths("M0 0H10V10L0 10Z") == [
            [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
        ]

    def test_each_move_starts_a_new_subpath(self) -> None:
        assert render_cli_banner.subpaths("M59 115L83 91L59 67M91 123H123") == [
            [(59.0, 115.0), (83.0, 91.0), (59.0, 67.0)],
            [(91.0, 123.0), (123.0, 123.0)],
        ]

    def test_a_cubic_curve_is_flattened_to_its_end_point(self) -> None:
        (points,) = render_cli_banner.subpaths("M0 0C0 10 10 10 10 0")

        assert (points[0], points[-1]) == ((0.0, 0.0), (10.0, 0.0))

    def test_a_cubic_curve_follows_its_control_points(self) -> None:
        """With control points (0, 10) and (10, 10), y = 30s(1 - s): 7.5 at most."""
        (points,) = render_cli_banner.subpaths("M0 0C0 10 10 10 10 0")

        assert max(y for _, y in points) == pytest.approx(7.5, abs=0.01)

    def test_an_exponent_belongs_to_its_number(self) -> None:
        assert render_cli_banner.subpaths("M0 0L1e1 2.5E-1") == [
            [(0.0, 0.0), (10.0, 0.25)]
        ]

    def test_drawing_after_a_close_starts_at_the_closed_subpaths_start(
        self,
    ) -> None:
        """SVG 1.1 §8.3.3: after Z, the current point is the subpath's start."""
        assert render_cli_banner.subpaths("M10 10L20 10ZL20 20") == [
            [(10.0, 10.0), (20.0, 10.0)],
            [(10.0, 10.0), (20.0, 20.0)],
        ]

    def test_a_relative_command_is_refused(self) -> None:
        with pytest.raises(
            ValueError, match=re.escape("Unsupported SVG path command 'c'.")
        ):
            render_cli_banner.subpaths("M0 0c1 1 2 2 3 3")

    @pytest.mark.parametrize(
        "d",
        [
            pytest.param("L1 1", id="no-starting-move"),
            pytest.param("M0 0L1", id="too-few-numbers"),
            pytest.param("M", id="a-move-without-numbers"),
            pytest.param("M0 0L", id="a-command-without-numbers-at-the-end"),
            pytest.param("M0 0LH5", id="a-command-without-numbers-before-the-next"),
            pytest.param("M0 0Z5 5", id="numbers-after-close"),
        ],
    )
    def test_a_malformed_path_is_refused(self, d: str) -> None:
        with pytest.raises(ValueError, match="SVG path"):
            render_cli_banner.subpaths(d)


class TestLogoShapes:
    """docs/assets/boilerplate-cli-logo.svg, the banner's source.

    It draws eight bars, and the prompt as ``M59 115L83 91L59 67M91 123H123``.
    """

    def test_reads_the_eight_bars(self) -> None:
        shapes = render_cli_banner.logo_shapes(_LOGO.read_text(encoding="utf-8"))

        assert len(shapes.bars) == 8

    def test_reads_the_chevron_as_its_two_ends_and_its_tip(self) -> None:
        shapes = render_cli_banner.logo_shapes(_LOGO.read_text(encoding="utf-8"))

        assert shapes.chevron == ((59.0, 115.0), (83.0, 91.0), (59.0, 67.0))

    def test_reads_the_underscore_as_its_two_ends(self) -> None:
        shapes = render_cli_banner.logo_shapes(_LOGO.read_text(encoding="utf-8"))

        assert shapes.underscore == ((91.0, 123.0), (123.0, 123.0))

    def test_a_logo_without_its_braces_is_refused(self) -> None:
        """Their outlines are the SVG's paths filled brand blue (#40B4E5)."""
        logo = _LOGO.read_text(encoding="utf-8")
        svg = re.sub(r'<path d="[^"]*" fill="#40B4E5"/>', "", logo)

        with pytest.raises(ValueError, match="braces"):
            render_cli_banner.logo_shapes(svg)


class TestRenderLogo:
    def test_a_brace_ending_at_the_feet_stays_whole_above_the_underscore(
        self,
    ) -> None:
        """05 §Banner: the braces end on the cell row above the underscore's.

        In the SVG the underscore overlaps the right brace's foot. The art
        draws the underscore lower, on its own cell row, so a brace ending at
        the feet's height stays whole: this stand-in square brace, spanning
        x 100 to 120 and down to y=120, fills its cells in the row above.
        """
        square = np.array(
            [(100.0, 100.0), (120.0, 100.0), (120.0, 120.0), (100.0, 120.0)]
        )
        shapes = render_cli_banner.logo_shapes(_LOGO.read_text(encoding="utf-8"))

        rows = render_cli_banner.render_logo(shapes._replace(braces=[square]), 25)

        assert rows[9][0][20:23] == "⣿⣿⣿"


class TestOneColorPerCell:
    """A cell holding a prompt dot drops its blue dots (05 §Banner)."""

    def test_blue_dots_sharing_a_cell_with_the_prompt_are_dropped(self) -> None:
        empty, blue, prompt = 0, 1, 2
        grid = np.zeros((4, 4), dtype=np.int8)
        grid[0, 0] = prompt
        grid[3, 1] = blue  # same cell as the prompt dot
        grid[0, 2] = blue  # a cell of its own

        resolved = render_cli_banner.one_color_per_cell(grid)

        assert (resolved[3, 1], resolved[0, 2], resolved[0, 0]) == (empty, blue, prompt)


class TestLightBars:
    """Light a bar's two dot rows together in each column (05 §Banner).

    A column lights when the bar covers at least half of its two rows'
    samples, as a stroke's dot lights at half its samples.
    """

    def test_a_column_covered_half_across_its_two_rows_lights_both(self) -> None:
        coverage = np.array([[0.0], [0.66], [0.41], [0.0]])

        lit = render_cli_banner.light_bars(coverage, [1])

        assert lit[:, 0].tolist() == [False, True, True, False]

    def test_a_column_covered_under_half_lights_neither(self) -> None:
        coverage = np.array([[0.48], [0.34]])

        lit = render_cli_banner.light_bars(coverage, [0])

        assert lit[:, 0].tolist() == [False, False]

    def test_rows_outside_the_bars_stay_dark(self) -> None:
        coverage = np.full((4, 1), 1.0)

        lit = render_cli_banner.light_bars(coverage, [0])

        assert lit[:, 0].tolist() == [True, True, False, False]


class TestModuleSource:
    def test_written_module_reproduces_the_art(self) -> None:
        name = ("| '_ \\", '"q"')
        logos = {22: [("⣿ ⠿", "b p")]}
        namespace: dict[str, object] = {}

        exec(render_cli_banner.module_source(name, logos), namespace)

        assert (namespace["NAME"], namespace["LOGOS"], namespace["LOGO_COLORS"]) == (
            name,
            {22: ("⣿ ⠿",)},
            {22: ("b p",)},
        )


class TestCommittedArt:
    def test_matches_a_fresh_render_of_the_logo(self) -> None:
        """banner_art.py is generated from the SVG: regenerate it after a change."""
        shapes = render_cli_banner.logo_shapes(_LOGO.read_text(encoding="utf-8"))
        logos = {
            width: render_cli_banner.render_logo(shapes, width)
            for width in render_cli_banner.WIDTHS
        }
        source = render_cli_banner.module_source(render_cli_banner.render_name(), logos)

        assert _ART.read_text(encoding="utf-8") == source


class TestMain:
    def test_help_exits_0(self) -> None:
        with pytest.raises(SystemExit) as exit_info:
            render_cli_banner.main(["--help"])

        assert exit_info.value.code == 0

    def test_help_prints_the_docstring(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit):
            render_cli_banner.main(["--help"])

        assert "Generate the CLI banner's art" in capsys.readouterr().out

    def test_an_unknown_option_is_a_usage_error(self) -> None:
        """Exit status 2 is argparse's usage error."""
        with pytest.raises(SystemExit) as exit_info:
            render_cli_banner.main(["--width", "25"])

        assert exit_info.value.code == 2
