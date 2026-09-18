"""Tests for the Boilerplate CLI entrypoint in cli.py."""

import io
import os
import subprocess
import sys

import pytest
from typer.testing import CliRunner

from boilerplate.cli import cli
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
    assert error_message in result.output
    assert error_message in result.output


def test_verbose_and_quiet_together_exit_with_validation_error(
    typer_cli_runner: CliRunner,
) -> None:
    """Tests that --verbose and --quiet together exit 3 (VALIDATION_ERROR)."""
    result = typer_cli_runner.invoke(cli.app, ["--verbose", "--quiet", "list"])
    assert result.exit_code == ExitCode.VALIDATION_ERROR


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

    def test_env_var_ci_implies_quiet_conflicts_with_verbose(
        self, monkeypatch: pytest.MonkeyPatch, typer_cli_runner: CliRunner
    ) -> None:
        """BOILERPLATE_CI forces --quiet, same as --ci, so it clashes with --verbose."""
        monkeypatch.setenv("BOILERPLATE_CI", "1")
        result = typer_cli_runner.invoke(cli.app, ["--verbose", "list"])
        assert result.exit_code == ExitCode.VALIDATION_ERROR


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
        sys.stdout.write(f"Composing: {sequence_text}\n")
        sys.stdout.flush()

        assert "Composing: project → streamlit" in stdout_buffer.getvalue().decode(
            "utf-8"
        )

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
