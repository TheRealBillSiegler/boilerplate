"""The streamlit layer carries a project's smoke test through its rename on update.

Copier's ``update`` removes every path the new template version stops rendering,
by name and without checking whether the project changed it, and its merge sees
a renamed file as added on both sides (docs/design/adr-007-update-model.md). The
layer's before-stage migration moves the old smoke test to its new name with
``git mv`` so the update surfaces the project's copy as a conflict carrying both
versions instead of deleting it. These tests compose a project from a tagged
repository of the layer and update that layer through the composition's merged
view, the way design 04's update walk does (Safe Update): the layer declares
only its own questions, so its paths and files take `project`'s answers from
the merged schema on every render an update performs.
"""

from pathlib import Path

import pytest
import yaml

from tests.boilerplate.templates.conftest import (
    TEMPLATES,
    commit_all,
    copy_layer_into,
    git,
    init_repo,
    rehome_layer,
    render,
    update_layer,
)

LAYER = TEMPLATES / "streamlit"
TEMPLATE_TEST_DIR = Path("tests/integration/{{ package_name }}")
RENDERED_TEST_DIR = Path("tests/integration/rehearsal_app")
OLD_TAG = "v0.1.0"
NEW_TAG = "v0.2.0"
ANSWERS: dict[str, object] = {
    "project_name": "rehearsal_app",
    "description": "Rehearsal project",
    "author_name": "Ada Lovelace",
    "author_email": "ada@example.com",
    "package_index_url": "",
    "container_registry": "ghcr.io",
}
USER_TEST = '\n\ndef test_user_added_this() -> None:\n    """Written in the project."""\n    assert True\n'


@pytest.fixture(scope="module")
def previous_release(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the layer's previous release as a plain directory in a templates dir.

    The previous release rendered the smoke test as ``tests_app.py`` and shipped
    no migrations. The parent directory stands in for ``--templates-dir``, so a
    compose resolves this copy ahead of the bundled layer.
    """
    layer = tmp_path_factory.mktemp("previous") / "streamlit"
    copy_layer_into(LAYER, layer)
    test_dir = layer / TEMPLATE_TEST_DIR
    (test_dir / "test_app.py.jinja").rename(test_dir / "tests_app.py.jinja")
    config_path = layer / "copier.yml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config.pop("_migrations", None)
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return layer


@pytest.fixture(scope="module")
def layer_repo(
    previous_release: Path, tmp_path_factory: pytest.TempPathFactory
) -> Path:
    """Build the layer's git history: the previous release, then the shipped one."""
    repo = tmp_path_factory.mktemp("repo") / "streamlit"
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
    project = render(
        "streamlit",
        tmp_path,
        context_data=ANSWERS,
        templates_dir=previous_release.parent,
    )
    rehome_layer(project, layer="streamlit", source=layer_repo, commit=OLD_TAG)
    init_repo(project)
    return project


def _update_to_shipped_release(project: Path, layer_repo: Path) -> None:
    update_layer(
        project, root="streamlit", layer="streamlit", source=layer_repo, ref=NEW_TAG
    )


@pytest.mark.slow
class TestRenamedSmokeTestMigration:
    def test_edited_smoke_test_survives_the_rename_as_a_conflict(
        self, previous_release: Path, layer_repo: Path, tmp_path: Path
    ) -> None:
        project = _project_at_previous_release(previous_release, layer_repo, tmp_path)
        old_test = project / RENDERED_TEST_DIR / "tests_app.py"
        old_test.write_text(
            old_test.read_text(encoding="utf-8") + USER_TEST, encoding="utf-8"
        )
        commit_all(project, "render plus a test written in the project")

        _update_to_shipped_release(project, layer_repo)

        new_test = project / RENDERED_TEST_DIR / "test_app.py"
        assert not old_test.exists()
        content = new_test.read_text(encoding="utf-8")
        assert "test_user_added_this" in content, "the project's edit is kept"
        assert "_warm_interpreter" in content, "the shipped release's test arrives"
        # The pause is visible to git, so mergetool and editors can resolve it.
        assert git(project, "ls-files", "-u", "--", RENDERED_TEST_DIR.as_posix())

    def test_migration_leaves_a_project_that_already_renamed_the_file_alone(
        self, previous_release: Path, layer_repo: Path, tmp_path: Path
    ) -> None:
        project = _project_at_previous_release(previous_release, layer_repo, tmp_path)
        commit_all(project, "render")
        git(
            project,
            "mv",
            "tests/integration/rehearsal_app/tests_app.py",
            "tests/integration/rehearsal_app/test_app.py",
        )
        commit_all(project, "renamed by hand ahead of the template")

        _update_to_shipped_release(project, layer_repo)

        assert (project / RENDERED_TEST_DIR / "test_app.py").exists()
        assert not (project / RENDERED_TEST_DIR / "tests_app.py").exists()
