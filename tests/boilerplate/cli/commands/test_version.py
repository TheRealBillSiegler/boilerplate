"""Tests for `boilerplate version` command."""

import pytest
from typer.testing import CliRunner

from boilerplate.cli import app


def test_cli_version_command(
    monkeypatch: pytest.MonkeyPatch, typer_cli_runner: CliRunner
) -> None:
    """Tests the version command through the CLI app."""
    monkeypatch.setattr("boilerplate.__version__", "9.9.9")
    result = typer_cli_runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "boilerplate 9.9.9" in result.output


def test_cli_version_command_with_unknown_version(
    monkeypatch: pytest.MonkeyPatch, typer_cli_runner: CliRunner
) -> None:
    """Tests the version command when version is 'Unknown'."""
    monkeypatch.setattr("boilerplate.__version__", "Unknown")
    result = typer_cli_runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "boilerplate Unknown" in result.output


def test_cli_version_command_with_dev_version(
    monkeypatch: pytest.MonkeyPatch, typer_cli_runner: CliRunner
) -> None:
    """Tests the version command with a development version string."""
    monkeypatch.setattr("boilerplate.__version__", "1.0.0-dev+git.abc123")
    result = typer_cli_runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "boilerplate 1.0.0-dev+git.abc123" in result.output
