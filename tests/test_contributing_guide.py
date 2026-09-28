"""Compare the contributing guides' claims against the config they describe.

`CONTRIBUTING.md` (repository root) quotes the ruff commands a contributor
runs locally and names who has decision authority. Both claims are checked
against the files that actually decide them -- the CI workflow and
`CODEOWNERS` -- so the guide cannot silently drift from either.
"""

from pathlib import Path
from typing import Final

REPO_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
CONTRIBUTING_MD: Final[Path] = REPO_ROOT / "CONTRIBUTING.md"
CI_WORKFLOW: Final[Path] = REPO_ROOT / ".github" / "workflows" / "ci.yml"
CODEOWNERS: Final[Path] = REPO_ROOT / "CODEOWNERS"


def _command_before_comment(line: str) -> str:
    """Return a shell command line with any trailing `#` comment stripped."""
    return line.split("#", 1)[0].strip()


def _find_command(text: str, prefix: str) -> str:
    """Return the first line in `text` starting with `prefix`, comment stripped."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(prefix):
            return _command_before_comment(stripped)
    raise AssertionError(f"no line starting with {prefix!r} found")


class TestLintCommandsMatchCiWorkflow:
    """CONTRIBUTING.md's quoted ruff commands must reproduce what CI runs.

    `pyproject.toml` sets `fix = true` project-wide, so a bare `ruff check`
    or `ruff format` silently rewrites files instead of failing on
    violations the way CI does.
    """

    def test_ruff_check_matches_ci(self) -> None:
        ci_command = (
            _find_command(
                CI_WORKFLOW.read_text(encoding="utf-8"), "- run: uv run ruff check"
            )
            .removeprefix("- run:")
            .strip()
        )
        doc_command = _find_command(
            CONTRIBUTING_MD.read_text(encoding="utf-8"), "uv run ruff check"
        )
        assert doc_command == ci_command, (
            f"CONTRIBUTING.md quotes {doc_command!r}, but ci.yml runs {ci_command!r}"
        )

    def test_ruff_format_matches_ci(self) -> None:
        ci_command = (
            _find_command(
                CI_WORKFLOW.read_text(encoding="utf-8"), "- run: uv run ruff format"
            )
            .removeprefix("- run:")
            .strip()
        )
        doc_command = _find_command(
            CONTRIBUTING_MD.read_text(encoding="utf-8"), "uv run ruff format"
        )
        assert doc_command == ci_command, (
            f"CONTRIBUTING.md quotes {doc_command!r}, but ci.yml runs {ci_command!r}"
        )


class TestDecisionAuthorityMatchesCodeowners:
    """CONTRIBUTING.md's decision-authority claim must match CODEOWNERS."""

    def test_root_contributing_names_the_single_maintainer(self) -> None:
        owners = [
            line.strip()
            for line in CODEOWNERS.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        assert len(owners) == 1, (
            "CODEOWNERS now lists more than one owner; CONTRIBUTING.md's "
            "singular 'maintainer' wording needs revisiting"
        )

        contributing_text = CONTRIBUTING_MD.read_text(encoding="utf-8")
        assert "maintainers listed in" not in contributing_text, (
            "CONTRIBUTING.md claims plural maintainers, but CODEOWNERS lists one"
        )
