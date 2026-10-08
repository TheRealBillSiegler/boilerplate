"""Tests for scripts/check.py's choice of whether to run the composition scenarios.

The local gate mirrors CI, whose ``changes`` job turns the scenarios job on when
the diff touches a composition path. The paths below are the ones
``.github/workflows/ci.yml`` lists, so a path that runs the scenarios in CI must
run them here. ``tests/`` has no ``__init__.py`` files anywhere, so this module
loads the script by path.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from check import scenario_choice, touches_composition

# One path under each entry of the CI workflow's composition list.
COMPOSITION_PATHS = [
    "src/boilerplate/composition/composer.py",
    "src/boilerplate/templates/project/copier.yml",
    "tests/integration/boilerplate/composition/scenarios/test_views.py",
    "tests/boilerplate/templates/conftest.py",
    "tests/fixtures/family/core/1.0.0/copier.yml",
    "uv.lock",
    ".github/workflows/ci.yml",
]


class TestTouchesComposition:
    """The paths that turn the scenarios on, as the CI workflow lists them."""

    @pytest.mark.parametrize("path", COMPOSITION_PATHS)
    def test_a_path_under_a_listed_entry_counts(self, path: str) -> None:
        """Count a path under any directory or equal to any file the workflow lists."""
        assert touches_composition([path]) is True

    @pytest.mark.parametrize(
        "path",
        [
            "src/boilerplate/cli/commands/new.py",
            "tests/integration/boilerplate/cli/test_new.py",
            "docs/governance/ci.md",
            "uv.lock.bak",
            ".github/workflows/release.yml",
            "src/boilerplate/composition_notes.md",
        ],
    )
    def test_a_path_outside_every_entry_does_not(self, path: str) -> None:
        """Ignore a path beside a listed entry: a sibling directory or file name."""
        assert touches_composition([path]) is False

    def test_one_listed_path_among_others_counts(self) -> None:
        """Count a change set when any one of its paths is listed."""
        assert touches_composition(["README.md", "uv.lock", "docs/index.md"]) is True

    def test_no_paths_do_not_count(self) -> None:
        """Skip an empty change set."""
        assert touches_composition([]) is False


class TestScenarioChoice:
    """Which choice the gate makes, and the reason it prints."""

    def test_an_unknown_merge_base_runs_them(self) -> None:
        """Run the scenarios when the merge base with origin/develop is unknown."""
        run, reason = scenario_choice(None, [])

        assert (run, "no merge base" in reason) == (True, True)

    def test_an_unreadable_diff_runs_them(self) -> None:
        """Run the scenarios when the diff against the merge base cannot be read."""
        run, reason = scenario_choice("abc1234", None)

        assert (run, "could not diff" in reason) == (True, True)

    def test_a_composition_path_runs_them_and_names_it(self) -> None:
        """Run the scenarios and say which path differs."""
        run, reason = scenario_choice("abc1234", ["README.md", "uv.lock"])

        assert (run, "uv.lock" in reason) == (True, True)

    def test_other_paths_skip_them(self) -> None:
        """Skip the scenarios when no changed path is a composition path."""
        run, reason = scenario_choice("abc1234", ["README.md", "docs/index.md"])

        assert (run, "no composition path" in reason) == (False, True)
