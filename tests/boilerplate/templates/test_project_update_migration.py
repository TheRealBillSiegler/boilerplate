"""The project layer keeps a project rendered before `build_backend` on hatchling.

Copier's ``update --defaults`` gives a question the project never answered its
template default, so a project rendered when the layer always built with
hatchling would move to ``uv_build`` and lose its ``[tool.hatch]`` table at
exit 0. The layer's before-stage migration records ``build_backend: hatchling``
in the project's answers file when that file holds no such answer, so the
update keeps the backend the project was built with. These tests compose a
project from a copy of the layer as it was before the question, then update
that layer under its scoped view. A composed `streamlit` project is updated
layer by layer, as an update walks it, to show that the layers after `project`
read the answer the migration just recorded.
"""

from pathlib import Path

import pytest
import yaml

from tests.boilerplate.templates.conftest import (
    TEMPLATES,
    build_layer_repo,
    commit_all,
    compose_project,
    copy_layer_into,
    git,
    init_repo,
    recorded_answers,
    rehome_layer,
    update_layer,
)

# Boilerplate finds a template by its folder name and names the layer's answers
# file after it, so every folder these tests build for the layer uses this name.
LAYER_NAME = "project"
LAYER = TEMPLATES / LAYER_NAME
OLD_TAG = "v0.1.0"
NEW_TAG = "v0.2.0"
ANSWERS: dict[str, object] = {
    "project_name": "rehearsal_app",
    "description": "Rehearsal project",
    "author_name": "Ada Lovelace",
    "author_email": "ada@example.com",
    "package_index_url": "",
}
PRE_QUESTION_BUILD_SYSTEM = (
    '[build-system]\nrequires = ["hatchling"]\nbuild-backend = "hatchling.build"\n'
)
PRE_QUESTION_WHEEL_TABLE = (
    '[tool.hatch.build.targets.wheel]\npackages = ["src/{{ package_name }}"]\n\n'
)


def _replace_between(text: str, start: str, end: str, replacement: str) -> str:
    """Replace the span from `start` up to, not including, `end` with `replacement`."""
    head, _, rest = text.partition(start)
    assert rest, f"{start!r} is missing from the template"
    assert end in rest, f"{end!r} is missing after {start!r}"
    _, _, tail = rest.partition(end)
    return head + replacement + end + tail


@pytest.fixture(scope="module")
def previous_release(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the layer as it was before the `build_backend` question.

    The previous release asked no such question, always built with hatchling,
    and shipped no migrations. The parent directory stands in for
    ``--templates-dir``, so a compose resolves this copy ahead of the bundled
    layer.
    """
    layer = tmp_path_factory.mktemp("previous") / LAYER_NAME
    copy_layer_into(LAYER, layer)
    config_path = layer / "copier.yml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config.pop("build_backend")
    config.pop("_migrations", None)
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    pyproject_path = layer / "pyproject.toml.jinja"
    pyproject = pyproject_path.read_text(encoding="utf-8")
    pyproject = _replace_between(
        pyproject, "[build-system]", "\n[project]", PRE_QUESTION_BUILD_SYSTEM
    )
    pyproject = _replace_between(
        pyproject,
        '{% if build_backend == "hatchling" -%}',
        "[tool.coverage.run]",
        PRE_QUESTION_WHEEL_TABLE,
    )
    pyproject_path.write_text(pyproject, encoding="utf-8")
    return layer


@pytest.fixture(scope="module")
def layer_repo(
    previous_release: Path, tmp_path_factory: pytest.TempPathFactory
) -> Path:
    """Build the layer's git history: the previous release, then the shipped one."""
    repo = tmp_path_factory.mktemp("repo") / LAYER_NAME
    copy_layer_into(previous_release, repo)
    init_repo(repo)
    commit_all(repo, "previous release", OLD_TAG)
    git(repo, "rm", "-r", "-q", ".")
    copy_layer_into(LAYER, repo)
    commit_all(repo, "shipped release", NEW_TAG)
    return repo


def _project_at_previous_release(
    previous_release: Path, layer_repo: Path, tmp_path: Path
) -> Path:
    """Compose with the previous release, then point the layer at its history."""
    project = tmp_path / "out"
    compose_project(LAYER_NAME, project, ANSWERS, previous_release.parent)
    rehome_layer(project, layer=LAYER_NAME, source=layer_repo, commit=OLD_TAG)
    init_repo(project)
    return project


def _update_to_shipped_release(
    project: Path, previous_release: Path, layer_repo: Path
) -> None:
    update_layer(
        project,
        root=LAYER_NAME,
        layer=LAYER_NAME,
        source=layer_repo,
        ref=NEW_TAG,
        templates={OLD_TAG: previous_release.parent, NEW_TAG: None},
    )


def _build_backend(project: Path) -> str:
    """Return the `build-backend` the project's `pyproject.toml` declares."""
    text = (project / "pyproject.toml").read_text(encoding="utf-8")
    (line,) = (line for line in text.splitlines() if line.startswith("build-backend"))
    return line.partition("=")[2].strip().strip('"')


@pytest.mark.slow
class TestBuildBackendMigration:
    def test_a_project_without_the_answer_stays_on_hatchling(
        self, previous_release: Path, layer_repo: Path, tmp_path: Path
    ) -> None:
        project = _project_at_previous_release(previous_release, layer_repo, tmp_path)
        commit_all(project, "render")
        assert _build_backend(project) == "hatchling.build"

        _update_to_shipped_release(project, previous_release, layer_repo)

        assert _build_backend(project) == "hatchling.build"
        assert recorded_answers(project, LAYER_NAME)["build_backend"] == "hatchling"
        assert "[tool.hatch.build.targets.wheel]" in (
            project / "pyproject.toml"
        ).read_text(encoding="utf-8")

    def test_a_recorded_answer_is_left_alone(
        self, previous_release: Path, layer_repo: Path, tmp_path: Path
    ) -> None:
        project = _project_at_previous_release(previous_release, layer_repo, tmp_path)
        answers = project / ".copier-answers.project.yml"
        answers.write_text(
            answers.read_text(encoding="utf-8") + "build_backend: uv_build\n",
            encoding="utf-8",
        )
        pyproject = project / "pyproject.toml"
        pyproject.write_text(
            pyproject.read_text(encoding="utf-8")
            .replace('requires = ["hatchling"]', 'requires = ["uv_build>=0.13,<0.14"]')
            .replace("hatchling.build", "uv_build")
            .replace(
                '[tool.hatch.build.targets.wheel]\npackages = ["src/rehearsal_app"]\n\n',
                "",
            ),
            encoding="utf-8",
        )
        commit_all(project, "render, then opt in to uv_build")

        _update_to_shipped_release(project, previous_release, layer_repo)

        assert _build_backend(project) == "uv_build"
        assert recorded_answers(project, LAYER_NAME)["build_backend"] == "uv_build"


STREAMLIT_LAYER_NAME = "streamlit"


@pytest.fixture(scope="module")
def streamlit_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the `streamlit` layer's git history: two releases of the shipped layer."""
    layer = TEMPLATES / STREAMLIT_LAYER_NAME
    return build_layer_repo(
        tmp_path_factory.mktemp("streamlit") / STREAMLIT_LAYER_NAME,
        {OLD_TAG: layer, NEW_TAG: layer},
    )


@pytest.mark.slow
class TestBuildBackendMigrationInAComposedUpdate:
    def test_the_layers_after_project_keep_the_backend_the_migration_recorded(
        self,
        previous_release: Path,
        layer_repo: Path,
        streamlit_repo: Path,
        tmp_path: Path,
    ) -> None:
        project = tmp_path / "out"
        compose_project(
            STREAMLIT_LAYER_NAME,
            project,
            {**ANSWERS, "container_registry": "ghcr.io"},
            previous_release.parent,
        )
        rehome_layer(project, layer=LAYER_NAME, source=layer_repo, commit=OLD_TAG)
        rehome_layer(
            project, layer=STREAMLIT_LAYER_NAME, source=streamlit_repo, commit=OLD_TAG
        )
        init_repo(project)
        commit_all(project, "render")
        assert _build_backend(project) == "hatchling.build"
        walk_answers = {
            layer: recorded_answers(project, layer)
            for layer in (LAYER_NAME, STREAMLIT_LAYER_NAME)
        }
        templates = {OLD_TAG: previous_release.parent, NEW_TAG: None}

        for layer, source in (
            (LAYER_NAME, layer_repo),
            (STREAMLIT_LAYER_NAME, streamlit_repo),
        ):
            update_layer(
                project,
                root=STREAMLIT_LAYER_NAME,
                layer=layer,
                source=source,
                ref=NEW_TAG,
                templates=templates,
                step_views=True,
                walk_answers=walk_answers,
            )
            commit_all(project, f"update {layer}")

        assert _build_backend(project) == "hatchling.build"
        assert recorded_answers(project, LAYER_NAME)["build_backend"] == "hatchling"
