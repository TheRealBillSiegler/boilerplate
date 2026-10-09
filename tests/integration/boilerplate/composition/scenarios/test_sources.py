"""Whether Boilerplate composes straight from layers that are git repositories.

S18 points the template catalog at the family's directory of git
repositories, one per layer, each tagged at its releases; it composes
``service`` over ``core``.
Copier's ``Template`` exposes ``git_index_modes`` for a git-backed template,
keyed by ``PurePosixPath``; the composer's JSON check rejects those keys.
"""

from pathlib import Path
from typing import NamedTuple

import pytest

from boilerplate.composition.serialization import yaml_utils
from boilerplate.integrations.copier_types import Template
from tests.boilerplate.templates.conftest import (
    compose,
    compose_project,
    render_full_view,
)
from tests.integration.boilerplate.composition.family import Family
from tests.integration.boilerplate.composition.scenarios.builders import (
    FAMILY_PROJECT,
    answers_file,
    run_boilerplate,
)

COMPOSED = ("core", "service")


class GitSources(NamedTuple):
    """A templates directory whose layers are git repositories."""

    templates_dir: Path
    repos: dict[str, Path]


@pytest.fixture(scope="module")
def git_sources(family: Family) -> GitSources:
    """Return the family's repositories, side by side, and the two composed."""
    return GitSources(
        family.repos["core"].parent, {layer: family.repos[layer] for layer in COMPOSED}
    )


@pytest.mark.xdist_group("S18")
class TestComposeFromGitSources:
    """S18: composing from git-repository layers."""

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "The composer's JSON check rejects Copier's path-keyed "
            "`git_index_modes`, so git-repository layers cannot compose; "
            "design 04 (Per-Layer Render Loop, step 1) and ADR-006 expect "
            "published first-party repositories to compose."
        ),
    )
    def test_compose_succeeds_from_git_repository_layers(
        self, git_sources: GitSources
    ) -> None:
        """S18: composing from layers that are git repositories succeeds."""
        compose("service", git_sources.templates_dir)

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "`new` exits 1 on the composer's JSON-check error for git-repository "
            "layers; design 04 (Per-Layer Render Loop, step 1) and ADR-006 expect "
            "published first-party repositories to compose."
        ),
    )
    def test_new_exits_zero_from_git_repository_layers(
        self, git_sources: GitSources, tmp_path: Path
    ) -> None:
        """S18: `boilerplate new` from git-repository layers exits 0."""
        result = run_boilerplate(
            "new",
            "service",
            str(tmp_path / "family-app"),
            "--templates-dir",
            str(git_sources.templates_dir),
            "--non-interactive",
            "--no-tasks",
            "--data",
            f"project_name={FAMILY_PROJECT}",
        )

        assert result.returncode == 0

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
        tag, core 3.0.0 and service 1.1.0, as `_commit` and the repository as
        `_src_path`.
        """
        answers = {"project_name": FAMILY_PROJECT}
        original = yaml_utils.template_public_attr_names

        def without_git_index_modes(cls: type[Template]) -> frozenset[str]:
            return original(cls) - {"git_index_modes"}

        monkeypatch.setattr(
            yaml_utils, "template_public_attr_names", without_git_index_modes
        )
        project = tmp_path / "family-app"
        if compose_with == "full-view":
            render_full_view(
                "service",
                project,
                context_data=answers,
                templates_dir=git_sources.templates_dir,
            )
        else:
            compose_project("service", project, answers, git_sources.templates_dir)
        provenance = {
            layer: (
                answers_file(project, layer)["_commit"],
                Path(answers_file(project, layer)["_src_path"]),
            )
            for layer in COMPOSED
        }

        assert provenance == {
            "core": ("3.0.0", git_sources.repos["core"]),
            "service": ("1.1.0", git_sources.repos["service"]),
        }
