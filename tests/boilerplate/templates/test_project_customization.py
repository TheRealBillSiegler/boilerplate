"""Tests for the project template's customization Questions."""

from pathlib import Path

from boilerplate.cli.utils import build_template_catalog
from boilerplate.composition import Composer
from boilerplate.composition.rendering.engine import RenderEngine
from boilerplate.composition.rendering.models.execution_context import (
    ExecutionContext,
)
from boilerplate.composition.resolution import Resolver
from boilerplate.settings import Settings


def _render_project(
    tmp_path: Path,
    *,
    context_data: dict[str, object] | None = None,
    profile: dict[str, object] | None = None,
) -> Path:
    """Renders the project template with the given answer channels; returns dest dir.

    ``context_data`` is Copier's forced ``data`` channel; ``profile`` is the
    overridable ``user_defaults`` channel.
    """
    registry = build_template_catalog(None, Settings())
    resolution = Resolver().resolve("project", registry)
    composition = Composer().compose(resolution)
    dest = tmp_path / "out"
    ctx = ExecutionContext(
        destination=dest,
        context_data=context_data or {},
        profile=profile or {},
        overwrite=True,
        interactive=False,
        skip_tasks=True,
    )
    RenderEngine().render(composition, ctx)
    return dest


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
