"""Tests for scripts/check.py's choice of whether to run the composition scenarios.

The local gate mirrors CI, whose ``changes`` job turns the scenarios job on when
the diff touches a composition path. The paths below are the ones
``.github/workflows/ci.yml`` lists, copied here by hand, so a path that runs the
scenarios in CI must run them here. ``tests/`` has no ``__init__.py`` files
anywhere, so this module loads the script by path.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from check import scenario_choice, touches_composition

# One path under each entry of the CI workflow's composition list, and one in
# each package under ``src/boilerplate/`` (the scenarios run the whole CLI).
COMPOSITION_PATHS = [
    "src/boilerplate/cli/commands/new.py",
    "src/boilerplate/common/exceptions.py",
    "src/boilerplate/catalog/catalog.py",
    "src/boilerplate/composition/composer.py",
    "src/boilerplate/constants.py",
    "src/boilerplate/integrations/copier/runner.py",
    "src/boilerplate/models/layer.py",
    "src/boilerplate/repository/directory_repository.py",
    "src/boilerplate/settings/settings.py",
    "src/boilerplate/templates/project/copier.yml",
    "src/boilerplate/types/template_specifier.py",
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
            "tests/integration/boilerplate/cli/test_new.py",
            "docs/governance/ci.md",
            "uv.lock.bak",
            ".github/workflows/release.yml",
            "tests/integration/boilerplate/composition_notes.md",
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
        run, _ = scenario_choice(None, [])

        assert run is True

    def test_an_unknown_merge_base_says_so(self) -> None:
        """Name the missing merge base as the reason for running the scenarios."""
        _, reason = scenario_choice(None, [])

        assert "no merge base" in reason

    def test_an_unreadable_diff_runs_them(self) -> None:
        """Run the scenarios when the diff against the merge base cannot be read."""
        run, _ = scenario_choice("abc1234", None)

        assert run is True

    def test_an_unreadable_diff_says_so(self) -> None:
        """Name the failed diff as the reason for running the scenarios."""
        _, reason = scenario_choice("abc1234", None)

        assert "could not diff" in reason

    def test_a_composition_path_runs_them(self) -> None:
        """Run the scenarios when a changed path is a composition path."""
        run, _ = scenario_choice("abc1234", ["README.md", "uv.lock"])

        assert run is True

    def test_a_composition_path_is_named(self) -> None:
        """Say which composition path differs."""
        _, reason = scenario_choice("abc1234", ["README.md", "uv.lock"])

        assert "uv.lock" in reason

    def test_other_paths_skip_them(self) -> None:
        """Skip the scenarios when no changed path is a composition path."""
        run, _ = scenario_choice("abc1234", ["README.md", "docs/index.md"])

        assert run is False

    def test_other_paths_say_why(self) -> None:
        """Name the absence of a composition path as the reason for skipping."""
        _, reason = scenario_choice("abc1234", ["README.md", "docs/index.md"])

        assert "no composition path" in reason
