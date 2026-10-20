"""Tests for the streamlit template's customization Questions."""

import re
import shutil
import subprocess
import tomllib
from functools import partial
from pathlib import Path

import pytest

from tests.boilerplate.templates.conftest import render


def _posix_awk_shell() -> tuple[str, str] | None:
    """Return a bash plus a POSIX-mode awk command, or None when either is missing.

    mawk is Ubuntu's default awk; gawk in --posix mode reads regexes the same
    way. On Windows the bash is Git's, next to its gawk: the awk program holds
    a lone double quote, which Windows command-line quoting would mangle on
    the way to an MSYS program, so the lookup runs inside that bash instead.
    """
    if shutil.which("mawk"):
        awk = "mawk"
    elif gawk := shutil.which("gawk"):
        awk = "gawk --posix"
        sibling = Path(gawk).with_name("bash.exe")
        if sibling.is_file():
            return str(sibling), awk
    else:
        return None
    bash = shutil.which("bash")
    return (bash, awk) if bash else None


class TestDefaultImageName:
    r"""The container scripts find the project name under any POSIX awk.

    Seam: each rendered script's `get_project_name_from_pyproject`, run as
    written with `awk` bound to a POSIX-mode awk. With no `--image-name`, the
    script names the image after `[project] name` in pyproject.toml, the
    source of truth here. A GNU-only regex escape such as `\s` matches nothing
    under mawk, Ubuntu's default awk, so the README's plain
    `./scripts/build-container.sh` would tag the image `:local` and fail.
    """

    @pytest.mark.parametrize("script", ["build-container.sh", "push-container.sh"])
    def test_name_lookup_reads_the_project_name(self, tmp_path: Path, script: str):
        dest = render("streamlit", tmp_path)
        result = _run_name_lookup(dest, script)
        pyproject = tomllib.loads((dest / "pyproject.toml").read_text(encoding="utf-8"))
        assert result.stdout.strip() == pyproject["project"]["name"]

    @pytest.mark.parametrize("script", ["build-container.sh", "push-container.sh"])
    def test_name_lookup_fails_without_a_project_name(
        self, tmp_path: Path, script: str
    ):
        """An empty name would tag the image `:local`, so the lookup fails instead."""
        dest = render("streamlit", tmp_path)
        (dest / "pyproject.toml").write_text(
            '[project]\nversion = "0.1.0"\n', encoding="utf-8"
        )
        assert _run_name_lookup(dest, script).returncode != 0


def _run_name_lookup(dest: Path, script: str) -> subprocess.CompletedProcess[str]:
    """Run a rendered script's `get_project_name_from_pyproject` under a POSIX awk."""
    shell = _posix_awk_shell()
    if shell is None:
        pytest.skip("no bash with mawk or gawk on PATH")
    bash, awk = shell
    text = (dest / "scripts" / script).read_text(encoding="utf-8")
    lookup = re.search(
        r"^get_project_name_from_pyproject\(\) \{\n.*?^\}\n",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert lookup is not None
    program = f'awk() {{ command {awk} "$@"; }}\n{lookup.group(0)}get_project_name_from_pyproject\n'
    return subprocess.run(
        [bash, "-c", program], cwd=dest, capture_output=True, text=True, check=False
    )


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


class TestDockerfileUvTag:
    """The image's uv minor is the minor the project's `uv_build` range names.

    Seam: the streamlit render's `Dockerfile` and `pyproject.toml`. A uv older
    than the range's floor fetches `uv-build` from the package index, which
    fails offline with a cold cache, so the two move together. The test
    catches drift between the two values, not a minor both have left behind.
    """

    def test_tag_minor_equals_the_uv_build_range_minor(self, tmp_path: Path):
        dest = render("streamlit", tmp_path)
        tag = re.search(
            r"ghcr\.io/astral-sh/uv:(\d+\.\d+)\s",
            (dest / "Dockerfile").read_text(encoding="utf-8"),
        )
        pyproject = tomllib.loads((dest / "pyproject.toml").read_text(encoding="utf-8"))
        (requirement,) = pyproject["build-system"]["requires"]
        cap = re.fullmatch(r"uv_build>=(\d+\.\d+),<(\d+)\.(\d+)", requirement)
        assert tag, "the Dockerfile pins uv to a minor tag"
        assert cap, f"the default range names a uv minor: {requirement!r}"
        floor, cap_major, cap_minor = cap.groups()
        assert tag.group(1) == floor
        assert (int(cap_major), int(cap_minor)) == (
            int(floor.split(".")[0]),
            int(floor.split(".")[1]) + 1,
        )


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
