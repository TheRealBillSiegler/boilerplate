"""Tests for the project template's customization Questions."""

import json
import re
import subprocess
import tomllib
from functools import partial
from pathlib import Path

import pytest

from tests.boilerplate.templates.conftest import render, render_project

_render_project = partial(render, "project")


class TestFreeTextAnswers:
    """A free-text answer that would break the rendered TOML or Python is refused.

    Seam: the layer's questions, through a forced answer. The answers land
    inside double-quoted TOML strings in `pyproject.toml` and inside Python
    string literals, where a double quote, a backslash or a line break ends or
    escapes the string (TOML 1.0, "Basic strings"). Copier refuses an answer
    whose validator renders a message, with "Validation error for question
    '<name>'" (Copier's `Question.validate_answer`). Dropping a validator
    breaks this.
    """

    @pytest.mark.parametrize(
        "question", ["project_name", "description", "author_name", "author_email"]
    )
    @pytest.mark.parametrize(
        "value",
        ['A "fast" tool', "C:\\data", "Line one\nline two"],
        ids=["double-quote", "backslash", "line-break"],
    )
    def test_string_breaking_character_is_refused(
        self, tmp_path: Path, question: str, value: str
    ):
        with pytest.raises(
            ValueError, match=f"Validation error for question '{question}'"
        ):
            _render_project(tmp_path, context_data={question: value})

    def test_apostrophes_still_render_valid_toml(self, tmp_path: Path):
        dest = _render_project(
            tmp_path,
            context_data={"description": "It's fast", "author_name": "Seán O'Brien"},
        )
        project = tomllib.loads((dest / "pyproject.toml").read_text(encoding="utf-8"))[
            "project"
        ]
        assert (project["description"], project["authors"][0]["name"]) == (
            "It's fast",
            "Seán O'Brien",
        )


class TestProjectName:
    """A project name whose package Python cannot import is refused.

    Seam: the `project_name` question, through a forced answer. The package
    name is the slug with dashes as underscores, and an import statement
    needs an identifier that is not a keyword (Python reference, "Identifiers
    and keywords"). Dropping the validator breaks this.
    """

    @pytest.mark.parametrize(
        "name",
        ["2024 Report", "class", "!!!"],
        ids=["leading-digit", "keyword", "no-letters"],
    )
    def test_name_without_an_importable_package_is_refused(
        self, tmp_path: Path, name: str
    ):
        with pytest.raises(
            ValueError, match="Validation error for question 'project_name'"
        ):
            _render_project(tmp_path, context_data={"project_name": name})

    def test_folder_name_default_is_checked_too(self, tmp_path: Path):
        """The name defaults to the folder's, and Copier validates defaults as well."""
        with pytest.raises(
            ValueError, match="Validation error for question 'project_name'"
        ):
            render_project("project", tmp_path / "2024-analysis")

    def test_digits_after_a_letter_render(self, tmp_path: Path):
        dest = _render_project(tmp_path, context_data={"project_name": "Analysis 2024"})
        assert (dest / "src" / "analysis_2024" / "__init__.py").is_file()


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

    def test_turning_it_off_keeps_one_test(self, tmp_path: Path):
        """Without the sample, pytest still has a test to collect.

        pytest exits 5 when it collects nothing (pytest docs, "Exit codes"),
        which fails the README's `uv run pytest` and any CI built on it.
        """
        dest = render("project", tmp_path, context_data={"sample_module": False})
        package = dest.name.replace("-", "_")
        assert (dest / "tests" / package / "test_import.py").is_file()


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

    @pytest.mark.parametrize(
        "sample_module",
        [True, False],
        ids=["with-sample-module", "without-sample-module"],
    )
    def test_readme_quick_start_pytest_comment(
        self, tmp_path: Path, sample_module: bool
    ):
        dest = _render_project(tmp_path, context_data={"sample_module": sample_module})
        readme = (dest / "README.md").read_text(encoding="utf-8")
        assert re.search(r"^uv run pytest\s+# run the tests$", readme, re.MULTILINE)


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
