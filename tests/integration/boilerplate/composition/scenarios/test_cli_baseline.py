"""What the shipped `boilerplate new` writes today: the full-view baseline.

S21 runs the real CLI against the bundled layers. ``RenderEngine`` renders
every layer under the full view, so every layer's answers file records the
whole merged questionnaire; and there is no `update` command yet.
"""

import re
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import NamedTuple

import pytest
import yaml

from tests.integration.boilerplate.composition.scenarios.builders import (
    PROJECT_RECORDED,
    TEMPLATES,
    answers_file,
    check_bundled_questionnaire,
    temp_dir_inside,
)

ANSI = re.compile(r"\x1b\[[0-9;]*m")
LAYERS = ("project", "streamlit")


def bundled_version(layer: str) -> str:
    """Return the version a bundled layer's boilerplate.yml declares."""
    manifest = yaml.safe_load(
        (TEMPLATES / layer / "boilerplate.yml").read_text(encoding="utf-8")
    )
    return str(manifest["version"])


class NewRun(NamedTuple):
    """The `new` command's result and the project it wrote."""

    result: subprocess.CompletedProcess[str]
    project: Path


@pytest.fixture(scope="module")
def new_run(
    tmp_path_factory: pytest.TempPathFactory,
    subprocess_cli_runner: Callable[..., subprocess.CompletedProcess[str]],
) -> Iterator[NewRun]:
    """Run `boilerplate new streamlit` non-interactively with one answer."""
    check_bundled_questionnaire()
    root = tmp_path_factory.mktemp("cli")
    project = root / "probe-app"
    with temp_dir_inside(root):
        result = subprocess_cli_runner(
            "new",
            "streamlit",
            str(project),
            "--non-interactive",
            "--no-tasks",
            "--data",
            "project_name=Probe App",
            cwd=root,
        )
        yield NewRun(result, project)


@pytest.mark.xdist_group("S21")
class TestShippedNew:
    """S21: `boilerplate new streamlit` as shipped."""

    def test_new_succeeds(self, new_run: NewRun) -> None:
        """S21: the non-interactive compose exits 0."""
        assert new_run.result.returncode == 0

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "`new` renders every layer under the full merged view, so project's "
            "answers file records streamlit's questions; design 04 (Per-Layer "
            "Render Loop) and ADR-015 point 4 expect each file to record only "
            "its own layer's scoped view."
        ),
    )
    def test_each_answers_file_records_only_its_layers_scoped_view(
        self, new_run: NewRun
    ) -> None:
        """S21: project's file lacks streamlit's question; streamlit's has both."""
        keys = {layer: set(answers_file(new_run.project, layer)) for layer in LAYERS}

        assert keys == {
            "project": PROJECT_RECORDED | {"_src_path"},
            "streamlit": PROJECT_RECORDED | {"container_registry", "_src_path"},
        }

    def test_bundled_layers_render_at_their_own_versions(self, new_run: NewRun) -> None:
        """S21: each bundled layer renders at its own boilerplate.yml version."""
        stderr = ANSI.sub("", new_run.result.stderr)
        rendered = re.findall(
            r"^Copying from template version (\S+)$", stderr, re.MULTILINE
        )

        assert rendered == [bundled_version(layer) for layer in LAYERS]

    def test_streamlit_overwrites_projects_readme(self, new_run: NewRun) -> None:
        """S21: the streamlit layer reports README as a conflict it overwrites."""
        reported = [
            line.split()
            for line in ANSI.sub("", new_run.result.stderr).splitlines()
            if line.strip().endswith("README.md")
        ]

        assert reported == [
            ["create", "README.md"],
            ["conflict", "README.md"],
            ["overwrite", "README.md"],
        ]


@pytest.mark.xfail(
    strict=True,
    reason=(
        "The CLI has no `update` command and exits 3; design 05 (update) "
        "specifies `boilerplate update`."
    ),
)
def test_update_help_exits_zero(
    tmp_path: Path,
    subprocess_cli_runner: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    """S21: `boilerplate update --help` exits 0."""
    result = subprocess_cli_runner("update", "--help", cwd=tmp_path)

    assert result.returncode == 0
