"""The streamlit layer carries a project's smoke test through its rename on update.

Copier's ``update`` removes every path the new template version stops rendering,
by name and without checking whether the project changed it, and its merge sees
a renamed file as added on both sides (docs/design/adr-007-update-model.md). The
layer's before-stage migration moves the old smoke test to its new name with
``git mv`` so the update surfaces the project's copy as a conflict carrying both
versions instead of deleting it. These tests drive vanilla ``copier update``
against a tagged repository of the layer, the way ADR-015's per-layer model does.
"""

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from copier import run_copy, run_update

from tests.boilerplate.templates.conftest import TEMPLATES

LAYER = TEMPLATES / "streamlit"
ANSWERS_FILE = ".copier-answers.streamlit.yml"
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


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=tests", "-c", "user.email=tests@example.com", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout


def _commit_all(repo: Path, message: str, tag: str | None = None) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    if tag:
        _git(repo, "tag", tag)


def _copy_layer_into(repo: Path) -> None:
    shutil.copytree(
        LAYER, repo, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__")
    )


@pytest.fixture(scope="module")
def layer_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the streamlit layer as a git repo: previous release, then shipped one.

    The previous release rendered the smoke test as ``tests_app.py`` and shipped
    no migrations; the shipped release is the layer as it exists in the tree.
    """
    repo = tmp_path_factory.mktemp("tpl-streamlit")
    _copy_layer_into(repo)
    _git(repo, "init", "-q", "-b", "main")
    test_dir = repo / TEMPLATE_TEST_DIR
    (test_dir / "test_app.py.jinja").rename(test_dir / "tests_app.py.jinja")
    config_path = repo / "copier.yml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config.pop("_migrations", None)
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    _commit_all(repo, "previous release", OLD_TAG)
    _git(repo, "rm", "-r", "-q", ".")
    _copy_layer_into(repo)
    _commit_all(repo, "shipped release", NEW_TAG)
    return repo


def _project_at_previous_release(layer_repo: Path, dest: Path) -> Path:
    run_copy(
        str(layer_repo),
        dest,
        data=ANSWERS,
        defaults=True,
        overwrite=True,
        quiet=True,
        skip_tasks=True,
        unsafe=True,
        vcs_ref=OLD_TAG,
    )
    _git(dest, "init", "-q", "-b", "main")
    return dest


def _update_to_shipped_release(project: Path) -> None:
    run_update(
        project,
        answers_file=ANSWERS_FILE,
        defaults=True,
        overwrite=True,
        quiet=True,
        skip_tasks=True,
        unsafe=True,
        vcs_ref=NEW_TAG,
    )


@pytest.mark.slow
class TestRenamedSmokeTestMigration:
    def test_edited_smoke_test_survives_the_rename_as_a_conflict(
        self, layer_repo: Path, tmp_path: Path
    ) -> None:
        project = _project_at_previous_release(layer_repo, tmp_path / "project")
        old_test = project / RENDERED_TEST_DIR / "tests_app.py"
        old_test.write_text(
            old_test.read_text(encoding="utf-8") + USER_TEST, encoding="utf-8"
        )
        _commit_all(project, "render plus a test written in the project")

        _update_to_shipped_release(project)

        new_test = project / RENDERED_TEST_DIR / "test_app.py"
        assert not old_test.exists()
        content = new_test.read_text(encoding="utf-8")
        assert "test_user_added_this" in content, "the project's edit is kept"
        assert "_warm_interpreter" in content, "the shipped release's test arrives"
        # The pause is visible to git, so mergetool and editors can resolve it.
        assert _git(project, "ls-files", "-u", "--", RENDERED_TEST_DIR.as_posix())

    def test_migration_leaves_a_project_that_already_renamed_the_file_alone(
        self, layer_repo: Path, tmp_path: Path
    ) -> None:
        project = _project_at_previous_release(layer_repo, tmp_path / "project")
        _commit_all(project, "render")
        _git(
            project,
            "mv",
            "tests/integration/rehearsal_app/tests_app.py",
            "tests/integration/rehearsal_app/test_app.py",
        )
        _commit_all(project, "renamed by hand ahead of the template")

        _update_to_shipped_release(project)

        assert (project / RENDERED_TEST_DIR / "test_app.py").exists()
        assert not (project / RENDERED_TEST_DIR / "tests_app.py").exists()
