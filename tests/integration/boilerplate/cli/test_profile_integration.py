"""End-to-end: profile.toml values reach the rendered project."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from boilerplate.cli.cli import app

runner = CliRunner()


def test_profile_toml_fills_project_questions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    profile = tmp_path / "profile.toml"
    profile.write_text(
        "[defaults]\n"
        'package_index_url = "https://pkgs.example.com/feed/pypi/simple/"\n'
        'author_name = "Jane Dev"\n'
    )
    monkeypatch.setattr(
        "boilerplate.settings.profile.profile_toml_path", lambda: profile
    )
    dest = tmp_path / "myapp"

    result = runner.invoke(app, ["new", "project", str(dest), "--yes", "--no-tasks"])

    assert result.exit_code == 0, result.output
    pyproject = (dest / "pyproject.toml").read_text()
    assert 'url = "https://pkgs.example.com/feed/pypi/simple/"' in pyproject
    assert 'name = "Jane Dev"' in pyproject


def test_without_profile_file_renders_public(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "boilerplate.settings.profile.profile_toml_path",
        lambda: tmp_path / "profile.toml",
    )
    dest = tmp_path / "myapp"

    result = runner.invoke(app, ["new", "project", str(dest), "--yes", "--no-tasks"])

    assert result.exit_code == 0, result.output
    assert "[[tool.uv.index]]" not in (dest / "pyproject.toml").read_text()
