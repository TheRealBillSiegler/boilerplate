"""Tests for the Boilerplate CLI entrypoint in cli.py."""

import io
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from boilerplate.cli import cli
from boilerplate.cli.display import ColorMode
from boilerplate.cli.seams import Seams
from boilerplate.composition.rendering.renderer import Renderer
from boilerplate.constants import ExitCode


def test_cli_runs_minimally_behavior(typer_cli_runner: CliRunner):
    """Tests that CLI shows help content when run without arguments."""
    # No args prints help/info and exits 0
    result = typer_cli_runner.invoke(cli.app, [])
    # Focus on behavior: help content is displayed
    assert "boilerplate" in result.output.lower()


def test_cli_verbose_enables_debug(
    monkeypatch: pytest.MonkeyPatch, typer_cli_runner: CliRunner
) -> None:
    """Tests that --verbose flag enables debug logging."""
    # Patch configure_logging and then invoke a real subcommand so callback runs
    called = {}

    def fake_configure_logging(debug: bool = False, ci: bool = False):
        called["debug"] = debug
        called["ci"] = ci

    monkeypatch.setattr(cli, "configure_logging", fake_configure_logging)

    # Pass --verbose *and* a subcommand (version) to exercise the callback
    result = typer_cli_runner.invoke(cli.app, ["--verbose", "version"])
    assert result.exit_code == 0
    assert called.get("debug") is True
    assert called.get("ci") is False


@pytest.mark.parametrize(
    "command,error_message",
    [
        (["version"], "boom"),
        (["new", "project"], "Settings initialization failed"),
    ],
)
def test_cli_handles_settings_error_behavior(
    monkeypatch: pytest.MonkeyPatch,
    typer_cli_runner: CliRunner,
    command: list[str],
    error_message: str,
) -> None:
    """Tests that CLI properly handles and reports settings initialization errors."""

    # Simulate Settings() raising, then call a subcommand
    def fake_settings():
        raise RuntimeError(error_message)

    monkeypatch.setattr(cli, "Settings", fake_settings)

    # Invoke command so main() is called and errors out
    result = typer_cli_runner.invoke(cli.app, command)
    # Focus on behavior: error message content and format
    assert f"Error: {error_message}" in result.output


def test_verbose_and_quiet_together_exit_with_validation_error(
    typer_cli_runner: CliRunner,
) -> None:
    """Tests that --verbose and --quiet together exit 3 (VALIDATION_ERROR)."""
    result = typer_cli_runner.invoke(cli.app, ["--verbose", "--quiet", "list"])
    assert result.exit_code == ExitCode.VALIDATION_ERROR


def _plain(output: str) -> str:
    """Strip ANSI style codes from CLI output.

    Typer forces color whenever ``GITHUB_ACTIONS`` is set, which puts escape
    codes inside its own error panels; the claims below are about the words.
    """
    return re.sub(r"\x1b\[[0-9;]*m", "", output)


class TestColorOption:
    """``--color`` accepts the three modes the design names and rejects the rest.

    Regression: the option was a plain string, so any other value (a typo such
    as ``--color nevr``, or ``--color NEVER``) was accepted and silently behaved
    as ``auto`` with exit code 0.
    """

    @pytest.fixture(autouse=True)
    def _terminal_like_stdout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Make the captured stdout behave like a terminal, deterministically.

        FORCE_COLOR is how Rich is told a stream is a terminal, so ``auto``
        can color it; the other variables are cleared so the developer's
        shell cannot flip a row. On a Windows process without VT support
        Rich sends fd 1 through its Win32 path, where escapes never reach
        captured text, and CliRunner's stdout reports the real fd; that
        detection is switched off at the library boundary.
        """
        for name in ("NO_COLOR", "TTY_COMPATIBLE", "BOILERPLATE_ACCESSIBLE"):
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setenv("FORCE_COLOR", "1")
        monkeypatch.setattr("rich.console.detect_legacy_windows", lambda: False)

    @pytest.mark.parametrize("mode", [m.value for m in ColorMode])
    def test_each_mode_is_accepted(
        self, typer_cli_runner: CliRunner, mode: str
    ) -> None:
        result = typer_cli_runner.invoke(cli.app, ["--color", mode, "version"])

        assert result.exit_code == ExitCode.SUCCESS, result.output

    @pytest.mark.parametrize("value", ["purple", "NEVER", ""])
    def test_any_other_value_is_rejected_naming_the_choices(
        self, typer_cli_runner: CliRunner, value: str
    ) -> None:
        result = typer_cli_runner.invoke(cli.app, ["--color", value, "version"])

        assert result.exit_code == ExitCode.VALIDATION_ERROR, result.output
        output = " ".join(_plain(result.output).split())
        assert "Invalid value for '--color'" in output
        # Rich wraps the panel, so the choices may not sit on one line.
        for choice in ("'auto'", "'always'", "'never'"):
            assert choice in output

    @pytest.mark.parametrize(
        ("flags", "colored"),
        [
            pytest.param([], True, id="default"),
            pytest.param(["--color", "auto"], True, id="auto"),
            pytest.param(["--color", "always"], True, id="always"),
            pytest.param(["--color", "never"], False, id="never"),
        ],
    )
    def test_the_mode_decides_whether_output_carries_color(
        self, typer_cli_runner: CliRunner, flags: list[str], colored: bool
    ) -> None:
        """On a terminal-like stdout, only never strips every escape code.

        auto colors a terminal, always forces color on, never forces it off,
        and the default is auto (Terminal Accessibility in
        docs/design/05-cli-reference.md). The bundled catalog supplies the
        styled table.
        """
        result = typer_cli_runner.invoke(cli.app, [*flags, "list"])

        assert result.exit_code == ExitCode.SUCCESS, result.output
        assert ("\x1b[" in result.output) is colored


class TestUsageErrorExitCode:
    """Every command-line usage error exits VALIDATION_ERROR, never CONFIG_ERROR.

    docs/design/02-data-models.md §Exit Codes reserves 2 for configuration that
    could not be loaded, so click's own default of 2 for usage errors would make
    a typo'd flag indistinguishable from a broken settings file. click still
    renders the message and its usage hint; only the code is ours.
    """

    @pytest.mark.parametrize(
        ("args", "expected_fragment"),
        [
            pytest.param(["--bogus-flag"], "No such option", id="root-unknown-option"),
            pytest.param(
                ["compose", "--bogus-flag", "project"],
                "No such option",
                id="subcommand-unknown-option",
            ),
            pytest.param(["compose"], "Missing argument", id="missing-argument"),
            pytest.param(["lisst"], "Did you mean", id="unknown-command"),
            pytest.param(
                ["compose", "project", "--sections", "bogus"],
                "Unknown section",
                id="in-body-bad-parameter",
            ),
        ],
    )
    def test_usage_errors_exit_validation_error(
        self, typer_cli_runner: CliRunner, args: list[str], expected_fragment: str
    ) -> None:
        """Parser-level and in-body usage errors both exit 3 and report themselves."""
        result = typer_cli_runner.invoke(cli.app, args)

        assert result.exit_code == ExitCode.VALIDATION_ERROR, result.output
        # Rich hard-wraps at console width, so compare on whitespace-normalized text.
        assert expected_fragment in " ".join(result.output.split())

    def test_usage_error_message_is_rendered_once(
        self, typer_cli_runner: CliRunner
    ) -> None:
        """Remapping the exit code does not add a second rendering of the message."""
        result = typer_cli_runner.invoke(cli.app, ["--bogus-flag"])

        assert " ".join(result.output.split()).count("No such option") == 1


class TestBoilerplateCiEnvVar:
    """BOILERPLATE_CI joins --ci with OR semantics; the generic CI is never read."""

    def _invoke_and_capture_ci_mode(
        self,
        monkeypatch: pytest.MonkeyPatch,
        typer_cli_runner: CliRunner,
        args: list[str],
    ) -> bool | None:
        called: dict[str, bool] = {}

        def fake_configure_logging(debug: bool = False, ci: bool = False) -> None:
            called["debug"] = debug
            called["ci"] = ci

        monkeypatch.setattr(cli, "configure_logging", fake_configure_logging)
        result = typer_cli_runner.invoke(cli.app, args)
        assert result.exit_code == 0, result.output
        return called.get("ci")

    @pytest.mark.parametrize("value", ["1", "banana"])
    def test_env_var_alone_triggers_ci_mode(
        self, monkeypatch: pytest.MonkeyPatch, typer_cli_runner: CliRunner, value: str
    ) -> None:
        """``banana`` is a garbage-but-truthy value per the spec's truthiness rule."""
        monkeypatch.setenv("BOILERPLATE_CI", value)
        assert (
            self._invoke_and_capture_ci_mode(monkeypatch, typer_cli_runner, ["version"])
            is True
        )

    @pytest.mark.parametrize("value", ["0", "false", "FALSE"])
    def test_env_var_zero_or_false_behaves_as_unset(
        self,
        monkeypatch: pytest.MonkeyPatch,
        typer_cli_runner: CliRunner,
        value: str,
    ) -> None:
        monkeypatch.setenv("BOILERPLATE_CI", value)
        assert (
            self._invoke_and_capture_ci_mode(monkeypatch, typer_cli_runner, ["version"])
            is False
        )

    def test_flag_and_env_var_compose(
        self, monkeypatch: pytest.MonkeyPatch, typer_cli_runner: CliRunner
    ) -> None:
        monkeypatch.setenv("BOILERPLATE_CI", "1")
        assert (
            self._invoke_and_capture_ci_mode(
                monkeypatch, typer_cli_runner, ["--ci", "version"]
            )
            is True
        )

    def test_generic_ci_env_var_is_a_no_op(
        self, monkeypatch: pytest.MonkeyPatch, typer_cli_runner: CliRunner
    ) -> None:
        """Regression: generic CI=true does not change --ci behavior (ADR-013)."""
        monkeypatch.setenv("CI", "true")
        assert (
            self._invoke_and_capture_ci_mode(monkeypatch, typer_cli_runner, ["version"])
            is False
        )

    def test_ci_and_verbose_combine(
        self, monkeypatch: pytest.MonkeyPatch, typer_cli_runner: CliRunner
    ) -> None:
        """CI mode does not imply --quiet, so a pipeline can ask for debug logs.

        --ci implies --non-interactive only and nothing about output volume.
        """
        called: dict[str, bool] = {}

        def fake_configure_logging(debug: bool = False, ci: bool = False) -> None:
            called.update(debug=debug, ci=ci)

        monkeypatch.setattr(cli, "configure_logging", fake_configure_logging)

        result = typer_cli_runner.invoke(cli.app, ["--ci", "--verbose", "version"])

        assert result.exit_code == ExitCode.SUCCESS, result.output
        assert called == {"debug": True, "ci": True}


class TestReconfigureStdioEncoding:
    """Regression tests for UnicodeEncodeError on legacy Windows codepages."""

    def test_legacy_codepage_stream_accepts_multi_layer_sequence_glyphs(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A cp1252 stdout renders the compose sequence arrow without raising."""
        stdout_buffer = io.BytesIO()
        stderr_buffer = io.BytesIO()
        monkeypatch.setattr(
            sys,
            "stdout",
            io.TextIOWrapper(stdout_buffer, encoding="cp1252", newline=""),
        )
        monkeypatch.setattr(
            sys,
            "stderr",
            io.TextIOWrapper(stderr_buffer, encoding="cp1252", newline=""),
        )

        cli._reconfigure_stdio_encoding()

        sequence_text = " → ".join(["project", "streamlit"])
        sys.stdout.write(f"Layers: {sequence_text}\n")
        sys.stdout.flush()

        assert "Layers: project → streamlit" in stdout_buffer.getvalue().decode("utf-8")

    def test_stream_already_utf8_is_left_untouched(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No redundant reconfigure when the stream already speaks UTF-8."""
        stdout_buffer = io.BytesIO()
        utf8_stdout = io.TextIOWrapper(stdout_buffer, encoding="utf-8", newline="")
        monkeypatch.setattr(sys, "stdout", utf8_stdout)

        cli._reconfigure_stdio_encoding()

        # errors stays at the TextIOWrapper default ("strict"); reconfigure()
        # was never called for a stream that was already UTF-8.
        assert sys.stdout.errors == "strict"

    def test_stream_without_reconfigure_is_skipped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Redirected/captured streams lacking reconfigure() do not raise."""
        monkeypatch.setattr(sys, "stdout", io.StringIO())

        cli._reconfigure_stdio_encoding()  # no AttributeError

    def test_real_interpreter_under_cp1252_pythonioencoding(self) -> None:
        """End-to-end: subprocess with PYTHONIOENCODING=cp1252 does not crash."""
        script = (
            "from boilerplate.cli.cli import _reconfigure_stdio_encoding;"
            "_reconfigure_stdio_encoding();"
            "import sys;"
            "sys.stdout.write(' → '.join(['project', 'streamlit']))"
        )
        env = {**os.environ, "PYTHONIOENCODING": "cp1252"}
        result = subprocess.run(
            [sys.executable, "-c", script],
            env=env,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0
        assert "project → streamlit".encode() in result.stdout


@pytest.mark.usefixtures("interactive_tty")
def test_a_renderer_passed_as_obj_reaches_the_new_command(
    typer_cli_runner: CliRunner,
    fake_template_dir: Path,
    temp_project_dir: Path,
    renderer: Renderer,
    seams: Seams,
) -> None:
    """A renderer injected via Click's `obj` is the one `new` drives.

    Exercises the seam end to end: `CliRunner.invoke(..., obj=seams)` sets
    `ctx.obj`; `main`'s `ctx.ensure_object(Seams)` picks it up; and
    `_bootstrap_runtime` threads `seams.renderer` into the `CliContext` the
    `new` command reads. `.claude/rules/tests.md` requires every patch to
    replace something at a boundary the code does not control — this seam
    exists so that boundary is Click's own `obj` mechanism instead of
    patching the command's engine import.
    """
    result = typer_cli_runner.invoke(
        cli.app,
        [
            "new",
            "mytpl",
            str(temp_project_dir),
            "--templates-dir",
            str(fake_template_dir),
        ],
        obj=seams,
    )

    assert result.exit_code == ExitCode.SUCCESS, result.output
    assert len(renderer.calls) == 1  # type: ignore[attr-defined]


# The last full row of FIGlet's standard "boilerplate", the banner's name.
_NAME_ROW = r"|_.__/ \___/|_|_|\___|_|  | .__/|_|\__,_|\__\___|"
_BRAILLE = re.compile("[\u2800-\u28ff]")


def _name_lines(output: str) -> list[str]:
    """Return the output lines that carry the banner's name row, unstyled."""
    return [line for line in _plain(output).splitlines() if _NAME_ROW in line]


@pytest.mark.usefixtures("banner_terminal")
class TestHelpBanner:
    """The top-level help opens with the banner on a terminal that can show it.

    docs/design/05-cli-reference.md §Banner.
    """

    @pytest.mark.parametrize("args", [[], ["--help"], ["-h"]], ids=str)
    def test_top_level_help_opens_with_the_name(
        self, typer_cli_runner: CliRunner, args: list[str]
    ) -> None:
        output = typer_cli_runner.invoke(cli.app, args).output

        assert output.index(_NAME_ROW) < output.index("Usage")

    def test_the_logo_sits_beside_the_name(self, typer_cli_runner: CliRunner) -> None:
        output = typer_cli_runner.invoke(cli.app, ["--help"]).output

        assert _BRAILLE.search(_name_lines(output)[0])

    @pytest.mark.parametrize(
        "args",
        [["--help"], ["--color", "never", "--help"]],
        ids=["logo-beside-name", "name-alone"],
    )
    def test_one_blank_line_comes_before_the_banner(
        self, typer_cli_runner: CliRunner, args: list[str]
    ) -> None:
        lines = _plain(typer_cli_runner.invoke(cli.app, args).output).splitlines()

        assert next(i for i, line in enumerate(lines) if line.strip()) == 1

    @pytest.mark.parametrize(
        "args",
        [
            ["--color", "never", "--help"],
            ["--help", "--color", "never"],
            ["--color=never", "--help"],
        ],
        ids=str,
    )
    def test_color_never_prints_the_name_without_the_logo(
        self, typer_cli_runner: CliRunner, args: list[str]
    ) -> None:
        output = typer_cli_runner.invoke(cli.app, args).output

        assert _name_lines(output) == [_NAME_ROW]

    def test_no_color_prints_the_name_without_the_logo(
        self, typer_cli_runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("NO_COLOR", "1")

        output = typer_cli_runner.invoke(cli.app, ["--help"]).output

        assert _name_lines(output) == [_NAME_ROW]

    def test_color_always_draws_the_logo_despite_no_color(
        self, typer_cli_runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An explicit --color wins over NO_COLOR (Terminal Accessibility rule 4)."""
        monkeypatch.setenv("NO_COLOR", "1")

        output = typer_cli_runner.invoke(cli.app, ["--color", "always", "-h"]).output

        assert _BRAILLE.search(_name_lines(output)[0])

    @pytest.mark.parametrize(
        ("args", "logo"),
        [
            pytest.param(
                ["--color", "always", "--color", "never", "-h"],
                False,
                id="last-never-wins",
            ),
            pytest.param(
                ["--color", "never", "--color", "always", "-h"],
                True,
                id="last-always-wins",
            ),
            pytest.param(["--color", "purple", "-h"], True, id="invalid-means-auto"),
            pytest.param(
                ["-h", "new", "--color", "never"], True, id="subcommand-args-ignored"
            ),
        ],
    )
    def test_the_banner_reads_the_last_root_color_flag(
        self, typer_cli_runner: CliRunner, args: list[str], logo: bool
    ) -> None:
        """Click keeps the last ``--color`` and parses only the root's own options."""
        output = typer_cli_runner.invoke(cli.app, args).output

        assert bool(_BRAILLE.search(_name_lines(output)[0])) is logo

    @pytest.mark.parametrize("args", [[], ["--help"]], ids=["bare", "--help"])
    def test_a_legacy_code_page_prints_the_name_without_the_logo(
        self, args: list[str]
    ) -> None:
        """Braille needs a UTF-8 stdout, judged before the CLI forces UTF-8 on it."""
        output = CliRunner(charset="cp1252").invoke(cli.app, args).output

        assert _name_lines(output) == [_NAME_ROW]

    @pytest.mark.parametrize(
        "variable", ["BOILERPLATE_NO_BANNER", "BOILERPLATE_ACCESSIBLE"]
    )
    def test_an_env_var_turns_it_off(
        self,
        typer_cli_runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
        variable: str,
    ) -> None:
        monkeypatch.setenv(variable, "1")

        output = typer_cli_runner.invoke(cli.app, ["--help"]).output

        assert _NAME_ROW not in output

    @pytest.mark.parametrize("args", [["new", "--help"], ["--version"]], ids=str)
    def test_subcommand_help_and_version_print_none(
        self, typer_cli_runner: CliRunner, args: list[str]
    ) -> None:
        output = typer_cli_runner.invoke(cli.app, args).output

        assert _NAME_ROW not in output


def test_help_piped_to_a_non_terminal_prints_no_banner(
    typer_cli_runner: CliRunner,
) -> None:
    """A piped --help stays plain (docs/design/05-cli-reference.md §Banner)."""
    output = typer_cli_runner.invoke(cli.app, ["--help"]).output

    assert _NAME_ROW not in output
