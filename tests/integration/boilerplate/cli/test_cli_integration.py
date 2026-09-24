"""End-to-end CLI tests through the Composer/RenderEngine/Copier stack.

Every test here drives `boilerplate` through Typer's `CliRunner` against a
tiny on-disk template and reads what Copier actually wrote — nothing patches
`compute_composition` or `RenderEngine`. Also covers exit codes for the
`graph`, `list`, `version`, and top-level help commands, which are real
end-to-end by construction (no rendering step to mock).
"""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from boilerplate.cli import app
from boilerplate.constants import ExitCode


def _write_template(
    directory: Path, name: str, version: str, extends: list[str] | None = None
) -> None:
    """Create a template directory with boilerplate.yml and copier.yml.

    No question or renderable body: sufficient for `graph`/`list`, which only
    read metadata, but not for `new`, which actually renders. Use
    `_write_renderable_template` for tests that invoke `new`.
    """
    template_dir = directory / name
    template_dir.mkdir(exist_ok=True)
    (template_dir / "copier.yml").touch()
    (template_dir / "boilerplate.yml").write_text(
        f"""
schema_version: "1.0.0"
name: "{name}"
description: "{name} template."
version: "{version}"
extends: {extends or []}
"""
    )


def _write_renderable_template(
    directory: Path, name: str = "tiny", *, question_default: str = "demo"
) -> Path:
    """Create a single-layer template Copier can actually render.

    One question (`project_name`, defaulting to `question_default`) and one
    Jinja file, so a real render produces an observable, deterministic file.

    Returns:
        The templates root directory (``directory``), suitable for
        ``--templates-dir``.
    """
    template_dir = directory / name
    template_dir.mkdir(parents=True)
    (template_dir / "boilerplate.yml").write_text(
        f"name: {name}\nversion: 1.0.0\n", encoding="utf-8"
    )
    (template_dir / "copier.yml").write_text(
        f"project_name:\n  type: str\n  default: {question_default}\n",
        encoding="utf-8",
    )
    (template_dir / "README.md.jinja").write_text(
        "# {{ project_name }}\n", encoding="utf-8"
    )
    return directory


class TestCLIExitCodeBehavior:
    """Exit codes for `graph`, `list`, and top-level commands (real, unmocked)."""

    def test_graph_command_list_exit_code(
        self, tmp_path: Path, typer_cli_runner: CliRunner
    ) -> None:
        """Tests graph command list format returns success."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        _write_template(templates_dir, "project", "1.0.0")

        result = typer_cli_runner.invoke(
            app, ["graph", "project", "--templates-dir", str(templates_dir)]
        )
        assert result.exit_code == ExitCode.SUCCESS
        assert "Layer" in result.output

    def test_graph_command_tree_exit_code(
        self, tmp_path: Path, typer_cli_runner: CliRunner
    ) -> None:
        """Tests graph command tree format returns success."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        _write_template(templates_dir, "project", "1.0.0")

        result = typer_cli_runner.invoke(
            app,
            [
                "graph",
                "project",
                "--templates-dir",
                str(templates_dir),
                "--format",
                "tree",
            ],
        )
        assert result.exit_code == ExitCode.SUCCESS
        assert "@" in result.output

    def test_graph_command_json_stdout_exit_code(
        self, tmp_path: Path, typer_cli_runner: CliRunner
    ) -> None:
        """Tests graph command JSON format to stdout returns success."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        _write_template(templates_dir, "project", "1.0.0")

        result = typer_cli_runner.invoke(
            app,
            [
                "graph",
                "project",
                "--templates-dir",
                str(templates_dir),
                "--format",
                "json",
            ],
        )
        assert result.exit_code == ExitCode.SUCCESS
        assert '"sequence"' in result.output

    def test_graph_command_validation_error_exit_code(
        self, tmp_path: Path, typer_cli_runner: CliRunner
    ) -> None:
        """Tests graph command validation error returns validation error exit code."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        _write_template(templates_dir, "project", "1.0.0")

        result = typer_cli_runner.invoke(
            app,
            [
                "graph",
                "project",
                "--templates-dir",
                str(templates_dir),
                "--output",
                "graph.json",
            ],
        )
        assert result.exit_code == ExitCode.VALIDATION_ERROR
        assert "Output option requires JSON format" in result.output

    def test_graph_command_json_file_output(
        self,
        tmp_path: Path,
        typer_cli_runner: CliRunner,
    ) -> None:
        """Tests graph command JSON output to file."""
        # Setup template directory
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        _write_template(templates_dir, "project", "1.0.0")

        # Run graph with JSON file output
        out_file = tmp_path / "graph.json"
        cmd = [
            "graph",
            "project",
            "--templates-dir",
            str(templates_dir),
            "--format",
            "json",
            "--output",
            str(out_file),
        ]
        result = typer_cli_runner.invoke(app, cmd)

        assert result.exit_code == ExitCode.SUCCESS
        assert out_file.exists()
        content = out_file.read_text(encoding="utf-8")
        assert '"sequence"' in content

    @pytest.mark.parametrize(
        "setup_scenario,expected_exit_code,expected_message",
        [
            ("with_templates", ExitCode.SUCCESS, "Description"),
            ("empty_dir", ExitCode.SUCCESS, "project"),
        ],
    )
    def test_templates_command_exit_codes(
        self,
        tmp_path: Path,
        typer_cli_runner: CliRunner,
        setup_scenario: str,
        expected_exit_code: ExitCode,
        expected_message: str | None,
    ) -> None:
        """Tests templates command exit codes for different scenarios."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        if setup_scenario == "with_templates":
            _write_template(templates_dir, "alpha", "1.0.0")
            _write_template(templates_dir, "beta", "2.0.0")
        # empty_dir scenario needs no additional setup

        result = typer_cli_runner.invoke(
            app, ["list", "--templates-dir", str(templates_dir)]
        )

        assert result.exit_code == expected_exit_code
        if expected_message:
            assert expected_message in result.output

    @pytest.mark.parametrize(
        "command,expected_exit_code,expected_content",
        [
            ([], ExitCode.SUCCESS, "boilerplate"),
            (["version"], ExitCode.SUCCESS, "boilerplate"),
        ],
    )
    def test_global_commands_exit_codes(
        self,
        typer_cli_runner: CliRunner,
        command: list[str],
        expected_exit_code: ExitCode,
        expected_content: str,
    ) -> None:
        """Tests global CLI commands return correct exit codes."""
        result = typer_cli_runner.invoke(app, command)

        assert result.exit_code == expected_exit_code
        assert expected_content in result.output


class TestNewCommandEndToEnd:
    """`new` exercised through the real CLI, Composer, RenderEngine, and Copier.

    Every test renders a tiny on-disk template with no mocked seams; the
    only test double is Click's `CliRunner` itself. Assertions read files
    Copier actually wrote, or the real error the production path emits.
    """

    def test_happy_path_renders_expected_files_and_content(
        self, tmp_path: Path, typer_cli_runner: CliRunner
    ) -> None:
        """A fresh destination renders successfully with real content on disk."""
        templates_root = _write_renderable_template(tmp_path / "templates")
        dest = tmp_path / "myproj"

        result = typer_cli_runner.invoke(
            app,
            [
                "new",
                "tiny",
                str(dest),
                "--non-interactive",
                "--no-tasks",
                "--templates-dir",
                str(templates_root),
            ],
        )

        assert result.exit_code == ExitCode.SUCCESS, result.output
        readme = dest / "README.md"
        assert readme.exists()
        assert readme.read_text(encoding="utf-8").strip() == "# demo"

    def test_template_not_found_returns_failure_with_real_error(
        self, tmp_path: Path, typer_cli_runner: CliRunner
    ) -> None:
        """A genuinely nonexistent template fails through the real catalog lookup."""
        result = typer_cli_runner.invoke(
            app,
            [
                "new",
                "definitely-does-not-exist",
                str(tmp_path / "output"),
                "--non-interactive",
            ],
        )

        assert result.exit_code == ExitCode.FAILURE, result.output
        normalized = " ".join(result.output.split())
        assert "not found" in normalized or "Template" in normalized

    def test_conflicting_destination_fails_then_force_overwrites(
        self, tmp_path: Path, typer_cli_runner: CliRunner
    ) -> None:
        """Documents the real (unmocked) behavior of a conflicting destination.

        Without `--force`, Copier detects the conflicting `README.md` and
        tries to prompt whether to overwrite it. That prompt needs a real
        console; CliRunner never provides one, so `RenderEngine` translates
        the failure to `InteractiveRenderFailedError`
        (`BP_RENDER_PROMPT_FAILED`, exit `FAILURE`) instead of the
        `--force`-suggesting message a mock previously injected. This is a
        real gap against docs/design/02-data-models.md's `DestinationNotEmptyError`
        contract (`BP_RENDER_DEST_NOT_EMPTY`, exit `VALIDATION_ERROR`), which
        is never actually raised by the render path — tracked, not fixed
        here.
        """
        templates_root = _write_renderable_template(tmp_path / "templates")
        dest = tmp_path / "existing_project"
        dest.mkdir()
        readme = dest / "README.md"
        readme.write_text("hand-authored, unrelated to the template", encoding="utf-8")

        result = typer_cli_runner.invoke(
            app,
            [
                "new",
                "tiny",
                str(dest),
                "--non-interactive",
                "--no-tasks",
                "--templates-dir",
                str(templates_root),
            ],
        )

        assert result.exit_code == ExitCode.FAILURE, result.output
        normalized = " ".join(result.output.split())
        assert "BP_RENDER_PROMPT_FAILED" in normalized
        assert (
            readme.read_text(encoding="utf-8")
            == "hand-authored, unrelated to the template"
        )

        result = typer_cli_runner.invoke(
            app,
            [
                "new",
                "tiny",
                str(dest),
                "--force",
                "--non-interactive",
                "--no-tasks",
                "--templates-dir",
                str(templates_root),
            ],
        )

        assert result.exit_code == ExitCode.SUCCESS, result.output
        assert readme.read_text(encoding="utf-8").strip() == "# demo"

    @pytest.mark.usefixtures("interactive_tty")
    def test_interactive_mode_renders_supplied_answer_through_real_copier(
        self, tmp_path: Path, typer_cli_runner: CliRunner
    ) -> None:
        """The interactive workflow (no `--non-interactive`) really invokes Copier.

        A live, typed-keystroke prompt cannot be driven through `CliRunner`:
        Copier's prompt layer (questionary/prompt_toolkit) needs a real
        console, which neither CI runners nor `CliRunner` ever provide.
        Confirmed empirically — bypassing only boilerplate's own TTY gate
        (what the `interactive_tty` fixture does) and letting an unanswered
        question actually reach Copier crashes with the same
        `InteractiveRenderFailedError` exercised in the test above, whether
        or not a console is faked. So this test proves the interactive
        workflow end-to-end the way it is actually exercisable: `new` is
        invoked without `--non-interactive` (the CLI's `interactive=True`
        path is real, not mocked), and the answer supplied on the
        forced-answer channel — not the template's own default — is what
        appears in the render, with no `input=` ever given to `CliRunner`.
        """
        templates_root = _write_renderable_template(
            tmp_path / "templates", question_default="template-default"
        )
        dest = tmp_path / "interactive_project"

        result = typer_cli_runner.invoke(
            app,
            [
                "new",
                "tiny",
                str(dest),
                "--no-tasks",
                "--data",
                "project_name=typed-answer",
                "--templates-dir",
                str(templates_root),
            ],
        )

        assert result.exit_code == ExitCode.SUCCESS, result.output
        readme = dest / "README.md"
        assert readme.read_text(encoding="utf-8").strip() == "# typed-answer"


class TestTopLevelHelp:
    """Top-level CLI behavior when no subcommand is provided."""

    def test_invoking_without_subcommand_prints_help_and_exits_successfully(
        self,
        typer_cli_runner: CliRunner,
    ) -> None:
        """Invoking with no subcommand shows help and exits with success."""
        result = typer_cli_runner.invoke(app, [])
        assert result.exit_code == ExitCode.SUCCESS, (
            f"Expected success exit code when showing help, got {result.exit_code}. "
            f"Output: {result.output}"
        )
        # Help should include app description, command groups, and all commands
        assert "boilerplate" in result.output.lower()
        assert "Use a template" in result.output
        assert "Author a template" in result.output
        assert "About" in result.output
        for cmd in ("version", "list", "new", "graph", "compose"):
            assert cmd in result.output

    def test_verbose_without_subcommand_still_shows_help_and_success(
        self,
        typer_cli_runner: CliRunner,
    ) -> None:
        """--verbose with no subcommand still prints help and succeeds."""
        result = typer_cli_runner.invoke(app, ["--verbose"])
        assert result.exit_code == ExitCode.SUCCESS
        assert "boilerplate" in result.output.lower()
