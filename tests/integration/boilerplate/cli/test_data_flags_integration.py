"""End-to-end: `--data`/`--data-file` reach questions that have no default.

Renders a hand-built, single-layer template (not the shipped ones, which
give every question a default) through the real CLI and RenderEngine — no
mocked Copier Worker — because the behavior under test is Copier's own
forced-answers (`data`) channel, not boilerplate's orchestration code.
"""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from boilerplate.cli.cli import app
from boilerplate.constants import ExitCode

runner = CliRunner()


def _write_needs_answer_template(root: Path) -> Path:
    """Write a single-layer template with one question that has no default."""
    tpl_dir = root / "needsanswer"
    tpl_dir.mkdir(parents=True)
    (tpl_dir / "boilerplate.yml").write_text(
        "name: needsanswer\nversion: 1.0.0\n", encoding="utf-8"
    )
    (tpl_dir / "copier.yml").write_text(
        "required_field:\n  type: str\n  help: A field with no default\n",
        encoding="utf-8",
    )
    (tpl_dir / "answer.txt.jinja").write_text(
        "{{ required_field }}\n", encoding="utf-8"
    )
    return root


class TestDataSatisfiesMissingRequiredAnswer:
    def test_non_interactive_fails_without_an_answer(self, tmp_path: Path):
        """Baseline: the pre-flight this feature is meant to satisfy."""
        templates_root = _write_needs_answer_template(tmp_path / "templates")
        dest = tmp_path / "out"

        result = runner.invoke(
            app,
            [
                "new",
                "needsanswer",
                str(dest),
                "--non-interactive",
                "--no-tasks",
                "--templates-dir",
                str(templates_root),
            ],
        )

        assert result.exit_code == ExitCode.VALIDATION_ERROR, result.output
        assert "BP_INPUT_ANSWERS_MISSING" in result.output

    def test_data_flag_satisfies_non_interactive_render(self, tmp_path: Path):
        templates_root = _write_needs_answer_template(tmp_path / "templates")
        dest = tmp_path / "out"

        result = runner.invoke(
            app,
            [
                "new",
                "needsanswer",
                str(dest),
                "--non-interactive",
                "--no-tasks",
                "--data",
                "required_field=from-flag",
                "--templates-dir",
                str(templates_root),
            ],
        )

        assert result.exit_code == ExitCode.SUCCESS, result.output
        assert (dest / "answer.txt").read_text(encoding="utf-8").strip() == "from-flag"

    def test_data_file_flag_satisfies_non_interactive_render(self, tmp_path: Path):
        templates_root = _write_needs_answer_template(tmp_path / "templates")
        dest = tmp_path / "out"
        data_file = tmp_path / "answers.yml"
        data_file.write_text("required_field: from-file\n", encoding="utf-8")

        result = runner.invoke(
            app,
            [
                "new",
                "needsanswer",
                str(dest),
                "--non-interactive",
                "--no-tasks",
                "--data-file",
                str(data_file),
                "--templates-dir",
                str(templates_root),
            ],
        )

        assert result.exit_code == ExitCode.SUCCESS, result.output
        assert (dest / "answer.txt").read_text(encoding="utf-8").strip() == "from-file"

    def test_data_wins_over_data_file_and_profile(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Precedence: --data > --data-file > profile.toml pre-fills."""
        templates_root = _write_needs_answer_template(tmp_path / "templates")
        dest = tmp_path / "out"

        profile = tmp_path / "profile.toml"
        profile.write_text(
            '[templates.needsanswer]\nrequired_field = "from-profile"\n',
            encoding="utf-8",
        )
        monkeypatch.setattr(
            "boilerplate.settings.profile.profile_toml_path", lambda: profile
        )

        data_file = tmp_path / "answers.yml"
        data_file.write_text("required_field: from-file\n", encoding="utf-8")

        result = runner.invoke(
            app,
            [
                "new",
                "needsanswer",
                str(dest),
                "--non-interactive",
                "--no-tasks",
                "--data-file",
                str(data_file),
                "--data",
                "required_field=from-flag",
                "--templates-dir",
                str(templates_root),
            ],
        )

        assert result.exit_code == ExitCode.SUCCESS, result.output
        assert (dest / "answer.txt").read_text(encoding="utf-8").strip() == "from-flag"

    def test_data_file_wins_over_profile_without_data_flag(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        templates_root = _write_needs_answer_template(tmp_path / "templates")
        dest = tmp_path / "out"

        profile = tmp_path / "profile.toml"
        profile.write_text(
            '[templates.needsanswer]\nrequired_field = "from-profile"\n',
            encoding="utf-8",
        )
        monkeypatch.setattr(
            "boilerplate.settings.profile.profile_toml_path", lambda: profile
        )

        data_file = tmp_path / "answers.yml"
        data_file.write_text("required_field: from-file\n", encoding="utf-8")

        result = runner.invoke(
            app,
            [
                "new",
                "needsanswer",
                str(dest),
                "--non-interactive",
                "--no-tasks",
                "--data-file",
                str(data_file),
                "--templates-dir",
                str(templates_root),
            ],
        )

        assert result.exit_code == ExitCode.SUCCESS, result.output
        assert (dest / "answer.txt").read_text(encoding="utf-8").strip() == "from-file"


@pytest.mark.usefixtures("interactive_tty")
class TestInteractiveRenderDoesNotPromptForSuppliedAnswer:
    def test_data_answer_is_not_prompted_for_in_interactive_mode(self, tmp_path: Path):
        """Interactive is the default; --data does not block on stdin.

        No `input=` is given to CliRunner: if Copier attempted to prompt for
        `required_field`, reading from the empty stdin would raise instead
        of silently succeeding, failing this test.
        """
        templates_root = _write_needs_answer_template(tmp_path / "templates")
        dest = tmp_path / "out"

        result = runner.invoke(
            app,
            [
                "new",
                "needsanswer",
                str(dest),
                "--no-tasks",
                "--data",
                "required_field=from-flag",
                "--templates-dir",
                str(templates_root),
            ],
        )

        assert result.exit_code == ExitCode.SUCCESS, result.output
        assert (dest / "answer.txt").read_text(encoding="utf-8").strip() == "from-flag"
