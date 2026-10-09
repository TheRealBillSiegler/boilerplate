"""Project-owned files stay exactly as the project left them across an update.

A file listed in a layer's own `_skip_if_exists` is never merged into again
once the project has its own copy (docs/templates-hub/versioning.md §Authoring rules).
These tests compose a project from the bundled templates, point the layer
under test at a tagged repository of it, and update that layer through the
layer's scoped view, the way `test_streamlit_update_migration.py`
drives the smoke-test rename: render at a release, let the project rewrite
its project-owned files, ship a release that changes those same files, then
update and check the project's text survived byte for byte.

A companion class pins the corollary fact: `_skip_if_exists` only stops a
merge into an existing file. Copier still recreates one the project deleted,
so a file meant to be deleted (a sample module) must stay template-owned
instead — deleting it would not remove it for good.
"""

from pathlib import Path
from typing import NamedTuple

import pytest

from tests.boilerplate.templates.conftest import (
    TEMPLATES,
    commit_all,
    compose_project,
    copy_layer_into,
    init_repo,
    rehome_layer,
    update_layer,
)

PACKAGE = "rehearsal_app"
OLD_TAG = "v0.1.0"
NEW_TAG = "v0.2.0"
REWRITTEN_TEXT = "written in the project, never the template\n"


class ProjectOwnedFile(NamedTuple):
    """One project-owned file, named on both sides of the render.

    Attributes:
        rendered: Its path in a rendered project, package name resolved.
        source: Its path in the template source without the `.jinja`
            suffix, package name still the literal `{{ package_name }}`
            directory Copier renders.
    """

    rendered: str
    source: str


README = ProjectOwnedFile("README.md", "README.md")

PROJECT_ANSWERS: dict[str, object] = {
    "project_name": PACKAGE,
    "description": "Rehearsal project",
    "author_name": "Ada Lovelace",
    "author_email": "ada@example.com",
    "package_index_url": "",
}
STREAMLIT_ANSWERS: dict[str, object] = {
    **PROJECT_ANSWERS,
    "container_registry": "ghcr.io",
}

LAYER_CASES = [
    pytest.param(
        "project",
        PROJECT_ANSWERS,
        (
            README,
            ProjectOwnedFile(
                f"src/{PACKAGE}/__init__.py", "src/{{ package_name }}/__init__.py"
            ),
        ),
        id="project",
    ),
    pytest.param(
        "streamlit",
        STREAMLIT_ANSWERS,
        (
            README,
            ProjectOwnedFile(f"src/{PACKAGE}/app.py", "src/{{ package_name }}/app.py"),
            ProjectOwnedFile(
                f"tests/integration/{PACKAGE}/test_app.py",
                "tests/integration/{{ package_name }}/test_app.py",
            ),
        ),
        id="streamlit",
    ),
]


def _bump_release(repo: Path, project_owned: tuple[ProjectOwnedFile, ...]) -> None:
    """Change every project-owned file's template source, as a release would.

    Args:
        repo: The layer's git working tree.
        project_owned: Files whose `.jinja` source to edit.
    """
    for owned in project_owned:
        source = repo / f"{owned.source}.jinja"
        source.write_text(
            source.read_text(encoding="utf-8") + "\n# next release\n",
            encoding="utf-8",
        )


def _build_layer_repo(
    layer: str, tmp_path: Path, project_owned: tuple[ProjectOwnedFile, ...]
) -> Path:
    """Build a tagged git repo for the bundled `layer`: `OLD_TAG`, then `NEW_TAG`.

    Args:
        layer: The bundled layer's name.
        tmp_path: Pytest's per-test temp directory to build the repo under.
        project_owned: Files a release at `NEW_TAG` changes.

    Returns:
        The git working tree, tagged at both `OLD_TAG` and `NEW_TAG`.
    """
    repo = tmp_path / "layer_repo"
    copy_layer_into(TEMPLATES / layer, repo)
    init_repo(repo)
    commit_all(repo, "release", OLD_TAG)
    _bump_release(repo, project_owned)
    commit_all(repo, "next release", NEW_TAG)
    return repo


def _project_at_release(
    layer: str, repo: Path, answers: dict[str, object], tmp_path: Path
) -> Path:
    """Compose a project rooted at `layer`, then point that layer at `repo`.

    The bundled layer and the repository at `OLD_TAG` are the same content, so
    the composition renders the release the project is later updated from.
    """
    project = tmp_path / "out"
    compose_project(layer, project, answers)
    rehome_layer(project, layer=layer, source=repo, commit=OLD_TAG)
    init_repo(project)
    return project


def _update_to_next_release(project: Path, layer: str, repo: Path) -> None:
    # Both releases declare the bundled questions; only file contents change.
    update_layer(
        project,
        root=layer,
        layer=layer,
        source=repo,
        ref=NEW_TAG,
        templates={OLD_TAG: None, NEW_TAG: None},
    )


@pytest.mark.slow
class TestProjectOwnedFilesSurviveUpdate:
    @pytest.mark.parametrize(("layer", "answers", "project_owned"), LAYER_CASES)
    def test_rewritten_project_owned_files_survive_update(
        self,
        layer: str,
        answers: dict[str, object],
        project_owned: tuple[ProjectOwnedFile, ...],
        tmp_path: Path,
    ) -> None:
        repo = _build_layer_repo(layer, tmp_path, project_owned)
        project = _project_at_release(layer, repo, answers, tmp_path)

        for owned in project_owned:
            rendered = project / owned.rendered
            assert rendered.exists(), f"{owned.rendered} is rendered at {OLD_TAG}"
            rendered.write_text(REWRITTEN_TEXT, encoding="utf-8")
        commit_all(project, "project rewrites its owned files")

        _update_to_next_release(project, layer, repo)

        for owned in project_owned:
            content = (project / owned.rendered).read_text(encoding="utf-8")
            assert content == REWRITTEN_TEXT, (
                f"{owned.rendered} should survive the update byte for byte; "
                f"got {content!r}"
            )


@pytest.mark.slow
class TestDeletedProjectOwnedFileReturnsOnUpdate:
    """Pins that Copier recreates a deleted `_skip_if_exists` file on update.

    `_skip_if_exists` only stops a merge into an *existing* file; it does not
    make a deletion stick. This is why a sample meant to be deleted (unlike a
    README or an entry point, meant to be kept and rewritten) must stay
    template-owned instead of `_skip_if_exists`.
    """

    def test_deleted_readme_reappears_after_update(self, tmp_path: Path) -> None:
        repo = _build_layer_repo("project", tmp_path, (README,))
        project = _project_at_release("project", repo, PROJECT_ANSWERS, tmp_path)

        (project / "README.md").unlink()
        commit_all(project, "project deletes its README")

        _update_to_next_release(project, "project", repo)

        assert (project / "README.md").exists(), (
            "Copier recreates a deleted skip_if_exists file on update; if this "
            "fails, Copier's behavior changed and the docs guidance needs "
            "revisiting rather than being papered over"
        )
