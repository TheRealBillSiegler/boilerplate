"""Tests for the streamlit template's customization Questions."""

from pathlib import Path

from tests.boilerplate.templates.conftest import render


class TestContainerRegistry:
    def test_default_registry_is_ghcr(self, tmp_path: Path):
        dest = render("streamlit", tmp_path)
        push = (dest / "scripts" / "push-container.sh").read_text(encoding="utf-8")
        assert 'ACR_NAME="ghcr.io"' in push
        assert "_boilerplate" not in push

    def test_registry_override(self, tmp_path: Path):
        dest = render(
            "streamlit",
            tmp_path,
            context_data={"container_registry": "registry.example.com"},
        )
        push = (dest / "scripts" / "push-container.sh").read_text(encoding="utf-8")
        assert 'ACR_NAME="registry.example.com"' in push
        # container_registry feeds two sites; guard both against a stale one.
        assert "(default: registry.example.com)" in push


class TestBuildIndex:
    def test_build_script_defaults_to_public_index(self, tmp_path: Path):
        dest = render("streamlit", tmp_path)
        build = (dest / "scripts" / "build-container.sh").read_text(encoding="utf-8")
        assert "pypi.org/simple" in build
        assert "_boilerplate" not in build

    def test_build_script_uses_custom_index(self, tmp_path: Path):
        dest = render(
            "streamlit",
            tmp_path,
            context_data={
                "package_index_url": "https://pkgs.example.com/feed/pypi/simple/"
            },
        )
        build = (dest / "scripts" / "build-container.sh").read_text(encoding="utf-8")
        assert "pkgs.example.com/feed/pypi/simple" in build
