"""Whether Boilerplate composes straight from layers that are git repositories.

S18 points the template catalog at a directory whose ``project`` and
``streamlit`` layers are each a git repository tagged ``v1`` and ``v2``.
Copier's ``Template`` exposes ``git_index_modes`` for a git-backed template,
keyed by ``PurePosixPath``; the composer's JSON check rejects those keys.
"""

import os
import re
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

import pytest

from boilerplate.composition.serialization import yaml_utils
from boilerplate.integrations.copier_types import Template
from tests.integration.boilerplate.composition.scenarios.builders import (
    ANSWERS,
    answers_file,
    build_releases,
    build_repos,
    temp_dir_inside,
    write,
)
from tests.boilerplate.templates.conftest import (
    compose,
    compose_project,
    render_full_view,
)

REJECTED_KEY = (
    "JSON object keys must be strings, got PurePosixPath: "
    "PurePosixPath('.gitattributes')"
)


class GitSources(NamedTuple):
    """A templates directory whose layers are git repositories."""

    templates_dir: Path
    repos: dict[str, Path]


@pytest.fixture(scope="module")
def git_sources(tmp_path_factory: pytest.TempPathFactory) -> Iterator[GitSources]:
    """Build both layers as repositories tagged v1 and v2, side by side."""
    root = tmp_path_factory.mktemp("git-sources")

    def releases(ref: str, release: Path) -> None:
        write(release / "project" / "project_own.txt.jinja", f"release={ref}\n")

    with temp_dir_inside(root):
        repos = build_repos(root, build_releases(root, ("v1", "v2"), releases))
        yield GitSources(root / "repos", repos)


@pytest.mark.xdist_group("S18")
class TestComposeFromGitSources:
    """S18: composing from git-repository layers."""

    def test_compose_rejects_copiers_path_keyed_attribute(
        self, git_sources: GitSources
    ) -> None:
        """S18: the composer's JSON check fails on `git_index_modes`' path keys."""
        with pytest.raises(TypeError, match=re.escape(REJECTED_KEY)):
            compose("streamlit", git_sources.templates_dir)

    def test_new_exits_with_the_composers_error(
        self, git_sources: GitSources, tmp_path: Path
    ) -> None:
        """S18: `boilerplate new` exits 1 with the same message on stderr."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "boilerplate",
                "new",
                "streamlit",
                str(tmp_path / "probe-app"),
                "--templates-dir",
                str(git_sources.templates_dir),
                "--non-interactive",
                "--no-tasks",
                "--data",
                "project_name=Probe App",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            check=False,
        )

        assert (
            result.returncode,
            f"Error: {REJECTED_KEY}" in " ".join(result.stderr.split()),
        ) == (
            1,
            True,
        )

    @pytest.mark.parametrize("compose_with", ["full-view", "scoped-view"])
    def test_without_git_index_modes_both_composes_record_the_latest_tag(
        self,
        git_sources: GitSources,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        compose_with: str,
    ) -> None:
        """S18: without `git_index_modes` in the extracted attributes, compose works.

        A counterfactual, patched inside Boilerplate on purpose: it shows the
        attribute is the only blocker. Both layers then record the latest
        tag, v2, as `_commit` and the repository as `_src_path`.
        """
        original = yaml_utils.template_public_attr_names

        def without_git_index_modes(cls: type[Template]) -> frozenset[str]:
            return original(cls) - {"git_index_modes"}

        monkeypatch.setattr(
            yaml_utils, "template_public_attr_names", without_git_index_modes
        )
        project = tmp_path / "probe-app"
        if compose_with == "full-view":
            render_full_view(
                "streamlit",
                project,
                context_data=ANSWERS,
                templates_dir=git_sources.templates_dir,
            )
        else:
            compose_project("streamlit", project, ANSWERS, git_sources.templates_dir)
        provenance = {
            layer: (
                answers_file(project, layer)["_commit"],
                Path(answers_file(project, layer)["_src_path"]),
            )
            for layer in ("project", "streamlit")
        }

        assert provenance == {
            layer: ("v2", repo) for layer, repo in git_sources.repos.items()
        }
