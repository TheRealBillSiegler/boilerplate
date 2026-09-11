"""Tests for the streamlit template's customization Questions."""

from pathlib import Path

from tests.boilerplate.templates.conftest import render


class TestContainerRegistry:
    def test_default_registry_is_ghcr(self, tmp_path: Path):
        dest = render("streamlit", tmp_path)
        push = (dest / "scripts" / "push-container.sh").read_text(encoding="utf-8")
        assert 'REGISTRY="ghcr.io"' in push
        assert "(default: ghcr.io)" in push
        assert "_boilerplate" not in push

    def test_registry_override(self, tmp_path: Path):
        dest = render(
            "streamlit",
            tmp_path,
            context_data={"container_registry": "registry.example.com"},
        )
        push = (dest / "scripts" / "push-container.sh").read_text(encoding="utf-8")
        assert 'REGISTRY="registry.example.com"' in push
        # container_registry feeds two sites; guard both against a stale one.
        assert "(default: registry.example.com)" in push


class TestBuildIndex:
    def test_build_script_defaults_to_a_plain_build(self, tmp_path: Path):
        dest = render("streamlit", tmp_path)
        build = (dest / "scripts" / "build-container.sh").read_text(encoding="utf-8")
        assert "--secret" not in build
        assert "INDEX_URL" not in build
        assert "az " not in build
        assert "_boilerplate" not in build

    def test_build_script_requires_credentials_for_a_custom_index(self, tmp_path: Path):
        dest = render(
            "streamlit",
            tmp_path,
            context_data={
                "package_index_url": "https://pkgs.example.com/feed/pypi/simple/"
            },
        )
        build = (dest / "scripts" / "build-container.sh").read_text(encoding="utf-8")
        assert "INDEX_URL" in build
        assert "--secret id=index,env=INDEX" in build
        assert "az account get-access-token" not in build

    def test_build_script_uses_azure_tokens_for_an_azure_devops_index(
        self, tmp_path: Path
    ):
        dest = render(
            "streamlit",
            tmp_path,
            context_data={
                "package_index_url": "https://pkgs.dev.azure.com/acme/_packaging/feed/pypi/simple/"
            },
        )
        build = (dest / "scripts" / "build-container.sh").read_text(encoding="utf-8")
        assert "az account get-access-token" in build
        assert "pkgs.dev.azure.com/acme/_packaging/feed/pypi/simple" in build
        assert "--secret id=index,env=INDEX" in build


class TestDockerfileIndex:
    def test_dockerfile_defaults_to_a_plain_sync(self, tmp_path: Path):
        dest = render("streamlit", tmp_path)
        dockerfile = (dest / "Dockerfile").read_text(encoding="utf-8")
        assert "--mount=type=secret" not in dockerfile
        assert "uv sync --frozen --no-dev" in dockerfile

    def test_dockerfile_mounts_the_index_secret_for_a_custom_index(
        self, tmp_path: Path
    ):
        dest = render(
            "streamlit",
            tmp_path,
            context_data={
                "package_index_url": "https://pkgs.example.com/feed/pypi/simple/"
            },
        )
        dockerfile = (dest / "Dockerfile").read_text(encoding="utf-8")
        assert "--mount=type=secret,id=index,env=INDEX" in dockerfile
        assert '--default-index "$INDEX"' in dockerfile


class TestSampleModule:
    def test_sample_module_is_off_by_default(self, tmp_path: Path):
        dest = render("streamlit", tmp_path)
        package = dest / "src" / dest.name.replace("-", "_")
        assert not (package / "module.py").exists()
        assert not (dest / "tests" / package.name / "test_module.py").exists()
        assert (package / "app.py").is_file()

    def test_sample_module_can_be_turned_on(self, tmp_path: Path):
        dest = render("streamlit", tmp_path, context_data={"sample_module": True})
        package = dest / "src" / dest.name.replace("-", "_")
        assert (package / "module.py").is_file()
        assert (dest / "tests" / package.name / "test_module.py").is_file()
