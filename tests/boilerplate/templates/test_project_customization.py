"""Tests for the project template's customization Questions."""

import json
import re
import subprocess
from functools import partial
from pathlib import Path

from tests.boilerplate.templates.conftest import render

_render_project = partial(render, "project")


class TestPackageIndexUrl:
    def test_index_block_emitted_when_set(self, tmp_path: Path):
        dest = _render_project(
            tmp_path,
            context_data={
                "package_index_url": "https://pkgs.example.com/feed/pypi/simple/"
            },
        )
        pyproject = (dest / "pyproject.toml").read_text()
        assert "[[tool.uv.index]]" in pyproject
        assert 'url = "https://pkgs.example.com/feed/pypi/simple/"' in pyproject
        assert "default = true" in pyproject

    def test_no_index_block_by_default(self, tmp_path: Path):
        dest = _render_project(tmp_path)
        pyproject = (dest / "pyproject.toml").read_text()
        assert "[[tool.uv.index]]" not in pyproject


class TestVSCodeSettings:
    """`.vscode/settings.json` works unmodified on every OS.

    No hardcoded interpreter path — VS Code's Python extension auto-detects
    `.venv` in the workspace root.
    """

    def test_no_default_interpreter_path(self, tmp_path: Path):
        dest = _render_project(tmp_path)
        settings = (dest / ".vscode" / "settings.json").read_text()
        assert "python.defaultInterpreterPath" not in settings

    def test_no_os_specific_absolute_paths(self, tmp_path: Path):
        dest = _render_project(tmp_path)
        settings = (dest / ".vscode" / "settings.json").read_text()
        assert "Scripts" not in settings
        assert "bin/python" not in settings


class TestProfileIsOverridable:
    """A profile rides Copier's ``user_defaults`` channel.

    Applied when alone, overridden by a forced ``context_data`` value (the
    channel an interactive answer populates). The interactive prompt itself
    cannot run in CI, so overridability is proven through this precedence
    relationship.
    """

    def test_profile_applies_when_not_overridden(self, tmp_path: Path):
        dest = _render_project(
            tmp_path,
            profile={"package_index_url": "https://ud.example.com/simple/"},
        )
        pyproject = (dest / "pyproject.toml").read_text()
        assert 'url = "https://ud.example.com/simple/"' in pyproject

    def test_context_data_overrides_profile(self, tmp_path: Path):
        dest = _render_project(
            tmp_path,
            context_data={"package_index_url": "https://forced.example.com/simple/"},
            profile={"package_index_url": "https://ud.example.com/simple/"},
        )
        pyproject = (dest / "pyproject.toml").read_text()
        assert 'url = "https://forced.example.com/simple/"' in pyproject
        assert "ud.example.com" not in pyproject


class TestSampleModule:
    def test_sample_module_renders_by_default(self, tmp_path: Path):
        dest = render("project", tmp_path)
        package = dest / "src" / dest.name.replace("-", "_")
        assert (package / "module.py").is_file()
        assert (dest / "tests" / package.name / "test_module.py").is_file()

    def test_sample_module_can_be_turned_off(self, tmp_path: Path):
        dest = render("project", tmp_path, context_data={"sample_module": False})
        package = dest / "src" / dest.name.replace("-", "_")
        assert not (package / "module.py").exists()
        assert not (dest / "tests" / package.name / "test_module.py").exists()
        # An empty conditional name must vanish rather than leave a nameless file.
        assert all(path.name for path in dest.rglob("*"))
        assert not list(package.glob(".jinja"))


class TestRenderedListsAndReadme:
    def test_dependencies_render_one_per_line(self, tmp_path: Path):
        dest = _render_project(tmp_path, context_data={"dependencies": ["requests"]})
        pyproject = (dest / "pyproject.toml").read_text(encoding="utf-8")
        assert 'dependencies = [\n    "requests",\n]' in pyproject

    def test_readme_names_the_private_index_when_set(self, tmp_path: Path):
        dest = _render_project(
            tmp_path,
            context_data={
                "package_index_url": "https://pkgs.example.com/feed/pypi/simple/"
            },
        )
        readme = (dest / "README.md").read_text(encoding="utf-8")
        assert (
            "resolves packages from `https://pkgs.example.com/feed/pypi/simple/`"
            in readme
        )
        assert "Packages resolve from PyPI" not in readme

    def test_readme_points_at_pypi_by_default(self, tmp_path: Path):
        dest = _render_project(tmp_path)
        readme = (dest / "README.md").read_text(encoding="utf-8")
        assert "Packages resolve from PyPI" in readme

    def test_readme_quick_start_runs_tests_with_sample_module(self, tmp_path: Path):
        dest = _render_project(tmp_path, context_data={"sample_module": True})
        readme = (dest / "README.md").read_text(encoding="utf-8")
        assert re.search(r"^uv run pytest\s+# run the tests$", readme, re.MULTILINE)

    def test_readme_quick_start_notes_empty_suite_without_sample_module(
        self, tmp_path: Path
    ):
        dest = _render_project(tmp_path, context_data={"sample_module": False})
        readme = (dest / "README.md").read_text(encoding="utf-8")
        assert re.search(
            r"^uv run pytest\s+# run the tests \(empty until you add one\)$",
            readme,
            re.MULTILINE,
        )


class TestLineEndings:
    """The render stays LF everywhere, so its scripts run in WSL after any checkout.

    Without a `.gitattributes`, `core.autocrlf=true` rewrites every text file
    CRLF on the next checkout, and a CRLF shebang fails in bash.
    """

    def test_gitattributes_forces_lf_for_every_text_file(self, tmp_path: Path):
        dest = _render_project(tmp_path)
        attributes = (dest / ".gitattributes").read_text(encoding="utf-8")
        assert "* text=auto eol=lf" in attributes

    def test_checkout_under_autocrlf_keeps_files_lf(self, tmp_path: Path):
        dest = _render_project(tmp_path)
        git = [
            "git",
            "-c",
            "core.autocrlf=true",
            "-c",
            "user.name=tests",
            "-c",
            "user.email=tests@example.com",
        ]
        run = partial(subprocess.run, cwd=dest, check=True, capture_output=True)
        run([*git, "init", "-q", "-b", "main"])
        run([*git, "add", "-A"])
        run([*git, "commit", "-q", "-m", "render"])
        target = dest / "pyproject.toml"
        target.unlink()
        run([*git, "checkout", "--", "pyproject.toml"])
        assert b"\r" not in target.read_bytes()

    def test_editor_writes_lf(self, tmp_path: Path):
        dest = _render_project(tmp_path)
        settings = json.loads((dest / ".vscode" / "settings.json").read_text())
        assert settings["files.eol"] == "\n"

    def test_formatter_writes_lf(self, tmp_path: Path):
        dest = _render_project(tmp_path)
        pyproject = (dest / "pyproject.toml").read_text(encoding="utf-8")
        assert 'line-ending = "lf"' in pyproject
