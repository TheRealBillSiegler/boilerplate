"""Tests for the streamlit template's customization Questions."""

import subprocess
from functools import partial
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


class TestReadme:
    def test_default_readme(self, tmp_path: Path):
        dest = render("streamlit", tmp_path)
        readme = (dest / "README.md").read_text(encoding="utf-8")
        assert "tags and pushes to ghcr.io" in readme
        assert "--namespace <owner>" in readme
        assert "Packages resolve from PyPI" in readme
        assert "az acr login" not in readme
        assert "one test module per source module" not in readme

    def test_readme_for_an_azure_registry(self, tmp_path: Path):
        dest = render(
            "streamlit",
            tmp_path,
            context_data={"container_registry": "acme.azurecr.io"},
        )
        readme = (dest / "README.md").read_text(encoding="utf-8")
        assert "az acr login" in readme
        assert "--namespace" not in readme

    def test_readme_for_a_third_party_registry(self, tmp_path: Path):
        dest = render(
            "streamlit",
            tmp_path,
            context_data={"container_registry": "registry.example.com"},
        )
        readme = (dest / "README.md").read_text(encoding="utf-8")
        assert "assumes an existing" in readme
        assert "REGISTRY_TOKEN" not in readme

    def test_readme_for_a_custom_package_index(self, tmp_path: Path):
        dest = render(
            "streamlit",
            tmp_path,
            context_data={
                "package_index_url": "https://pkgs.example.com/feed/pypi/simple/"
            },
        )
        readme = (dest / "README.md").read_text(encoding="utf-8")
        assert "https://pkgs.example.com/feed/pypi/simple/" in readme
        assert "build secret" in readme

    def test_readme_for_a_sample_module(self, tmp_path: Path):
        dest = render("streamlit", tmp_path, context_data={"sample_module": True})
        readme = (dest / "README.md").read_text(encoding="utf-8")
        assert "module.py" in readme


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


class TestLineEndings:
    """The scripts stay LF through a Windows checkout, so they run in WSL and Linux.

    The `.gitattributes` comes from the project layer; this guards that the
    composition carries it into a streamlit render.
    """

    def test_scripts_stay_lf_after_an_autocrlf_checkout(self, tmp_path: Path):
        dest = render("streamlit", tmp_path)
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
        scripts = sorted((dest / "scripts").glob("*.sh"))
        assert scripts
        for script in scripts:
            script.unlink()
        run([*git, "checkout", "--", "scripts"])
        for script in scripts:
            assert b"\r" not in script.read_bytes(), script.name
