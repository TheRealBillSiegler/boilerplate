"""Tests for the streamlit template's customization Questions."""

from pathlib import Path

from boilerplate.cli.utils import build_template_catalog
from boilerplate.composition import Composer
from boilerplate.composition.rendering.engine import RenderEngine
from boilerplate.composition.rendering.models.execution_context import (
    ExecutionContext,
)
from boilerplate.composition.resolution import Resolver
from boilerplate.settings import Settings


def _render_streamlit(tmp_path: Path, context_data: dict[str, object]) -> Path:
    registry = build_template_catalog(None, Settings())
    resolution = Resolver().resolve("streamlit", registry)
    composition = Composer().compose(resolution)
    dest = tmp_path / "out"
    ctx = ExecutionContext(
        destination=dest,
        context_data=context_data,
        overwrite=True,
        interactive=False,
        skip_tasks=True,
    )
    RenderEngine().render(composition, ctx)
    return dest


class TestContainerRegistry:
    def test_default_registry_is_ghcr(self, tmp_path: Path):
        dest = _render_streamlit(tmp_path, {})
        push = (dest / "scripts" / "push-container.sh").read_text(encoding="utf-8")
        assert 'ACR_NAME="ghcr.io"' in push
        assert "_boilerplate" not in push

    def test_registry_override(self, tmp_path: Path):
        dest = _render_streamlit(
            tmp_path, {"container_registry": "registry.example.com"}
        )
        push = (dest / "scripts" / "push-container.sh").read_text(encoding="utf-8")
        assert 'ACR_NAME="registry.example.com"' in push
        # container_registry feeds two sites; guard both against a stale one.
        assert "(default: registry.example.com)" in push


class TestBuildIndex:
    def test_build_script_defaults_to_public_index(self, tmp_path: Path):
        dest = _render_streamlit(tmp_path, {})
        build = (dest / "scripts" / "build-container.sh").read_text(encoding="utf-8")
        assert "pypi.org/simple" in build
        assert "_boilerplate" not in build

    def test_build_script_uses_custom_index(self, tmp_path: Path):
        dest = _render_streamlit(
            tmp_path,
            {"package_index_url": "https://pkgs.example.com/feed/pypi/simple/"},
        )
        build = (dest / "scripts" / "build-container.sh").read_text(encoding="utf-8")
        assert "pkgs.example.com/feed/pypi/simple" in build
