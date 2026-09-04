"""Tests for `boilerplate templates` command."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from boilerplate.cli import app
from boilerplate.constants import ExitCode


def test_templates_list_output_behavior(tmp_path: Path, typer_cli_runner: CliRunner):
    """Tests that templates command produces expected table output format."""
    (tmp_path / "alpha").mkdir()
    (tmp_path / "alpha" / "copier.yml").touch()
    (tmp_path / "alpha" / "boilerplate.yml").write_text(
        """
schema_version: "1.0.0"
name: "alpha"
description: "Alpha template."
version: "1.0.0"
extends: []
"""
    )
    (tmp_path / "beta").mkdir()
    (tmp_path / "beta" / "copier.yml").touch()
    (tmp_path / "beta" / "boilerplate.yml").write_text(
        """
schema_version: "1.0.0"
name: "beta"
description: "Beta template."
version: "1.0.0"
extends: []
"""
    )
    result = typer_cli_runner.invoke(app, ["list", "--templates-dir", str(tmp_path)])
    # Focus on behavior: table content and structure
    assert "alpha" in result.output
    assert "beta" in result.output
    assert "Description" in result.output
    assert "Version" in result.output


def test_templates_empty_directory_still_lists_bundled(
    tmp_path: Path, typer_cli_runner: CliRunner
):
    """An empty --templates-dir adds nothing, and bundled templates still list.

    The flag adds to the search path rather than replacing it, so no fallback
    banner or re-query is involved (see docs/design/05-cli-reference.md).
    """
    result = typer_cli_runner.invoke(app, ["list", "--templates-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "project" in result.output
    assert "Bundled templates:" not in result.output


def test_templates_permission_error_behavior(
    monkeypatch: pytest.MonkeyPatch, typer_cli_runner: CliRunner, tmp_path: Path
) -> None:
    """Tests that templates command handles directory permission errors."""

    def raise_permission_error(_: object) -> None:
        raise PermissionError("blocked")

    monkeypatch.setattr(Path, "iterdir", raise_permission_error)
    result = typer_cli_runner.invoke(app, ["list", "--templates-dir", str(tmp_path)])
    # Focus on behavior: error handling and message propagation
    assert (
        "Configuration error" in result.output or "Permission denied" in result.output
    )


def test_templates_list_format_json_returns_wrapped_entries(
    tmp_path: Path, typer_cli_runner: CliRunner
):
    """`--format json` wraps entries in {"templates": [...]} with a fixed key set."""
    (tmp_path / "alpha").mkdir()
    (tmp_path / "alpha" / "copier.yml").touch()
    (tmp_path / "alpha" / "boilerplate.yml").write_text(
        """
schema_version: "1.0.0"
name: "alpha"
description: "Alpha template."
version: "1.0.0"
extends: []
"""
    )
    result = typer_cli_runner.invoke(
        app, ["list", "--templates-dir", str(tmp_path), "--format", "json"]
    )

    assert result.exit_code == ExitCode.SUCCESS
    payload = json.loads(result.output)
    assert "templates" in payload
    entries = {entry["name"]: entry for entry in payload["templates"]}
    assert "alpha" in entries
    assert set(entries["alpha"]) == {"name", "version", "description", "path"}


def test_templates_list_format_json_empty_catalog_reports_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, typer_cli_runner: CliRunner
):
    """An empty catalog under `--format json` fails closed with a JSON error body."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    monkeypatch.setenv("BOILERPLATE_DEFAULT_TEMPLATES_DIR", str(empty_dir))

    result = typer_cli_runner.invoke(
        app, ["list", "--templates-dir", str(empty_dir), "--format", "json"]
    )

    assert result.exit_code == ExitCode.FAILURE
    payload = json.loads(result.output)
    assert payload["templates"] == []
    assert "error" in payload
