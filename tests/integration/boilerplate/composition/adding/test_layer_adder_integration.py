"""``LayerAdder`` adds one family layer to a locked project, or refuses to.

The expected behavior is design 05 §add and design 06 §Adding a layer: the
preconditions, their errors and remedies, the result as uncommitted changes, the
lock with the layer last, the migration record, the layer's own tasks and the
keep-or-undo handling of a failed task.
"""

import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any, NamedTuple

import pytest

from boilerplate.common.exceptions import (
    AddAncestorsMissingError,
    AddAncestorVersionError,
    BoilerplateError,
    LayerAlreadyAddedError,
    ProjectNotManagedError,
    UpdateProjectNotReadyError,
    UpdateTaskFailedError,
)
from boilerplate.composition.adding import (
    AddOutcome,
    AddRequest,
    AddStatus,
    LayerAdder,
)
from boilerplate.composition.staging.stale_cleanup import STAGING_PREFIX
from boilerplate.composition.updating.failed_task import FailedTask
from boilerplate.composition.updating.task_failure_choice import TaskFailureChoice
from boilerplate.models import MigrationStatus
from boilerplate.project_state.lock_file import LOCK_FILE_NAME, read_lock
from boilerplate.project_state.migrations_file import MIGRATIONS_FILE, read_migrations
from tests.boilerplate.templates.conftest import commit_all, git
from tests.integration.boilerplate.composition.adding.layers import build_layer
from tests.integration.boilerplate.composition.family import Family
from tests.integration.boilerplate.composition.scenarios.builders import (
    answers_file,
    compose_locked_family,
    lines,
    tree,
)
from tests.integration.boilerplate.composition.temp_dir import temp_dir_inside

BASE = {"core": "1.0.0", "service": "1.0.0"}
OPERATION_TASK = """\
_tasks:
  - command:
      - "{{ _copier_python }}"
      - -c
      - "print('{{ _copier_operation }}', file=open('.tasked-marker', 'a', encoding='utf-8'))"
"""
FAILING_TASK = """\
_tasks:
  - command:
      - "{{ _copier_python }}"
      - -c
      - "raise SystemExit(3)"
"""
SECRET_TASK = """\
deploy_token:
  type: str
  secret: true
  default: ""

_tasks:
  - command:
      - "{{ _copier_python }}"
      - -c
      - "print('{{ deploy_token }}', file=open('.token-marker', 'a', encoding='utf-8'))"
"""


def ask(
    family: Family,
    name: str,
    ref: str | None = None,
    supplied: dict[str, Any] | None = None,
    no_tasks: bool = False,
) -> AddRequest:
    """Build the request that adds family layer `name` at `ref`."""
    return AddRequest(
        name=name,
        source=family.repos[name].as_posix(),
        ref=ref,
        supplied=supplied or {},
        no_tasks=no_tasks,
    )


def head(project: Path) -> str:
    """Return the commit the checkout is at."""
    return git(project, "rev-parse", "HEAD").strip()


def status(project: Path) -> str:
    """Return git's porcelain status of the checkout."""
    return git(project, "status", "--porcelain")


def ask_built(project: Path, name: str, **options: bool) -> AddRequest:
    """Build the request that adds the one-off layer `name` built beside `project`."""
    return AddRequest(
        name=name, source=(project.parent / "repos" / name).as_posix(), **options
    )


def undo(_failed: FailedTask) -> TaskFailureChoice:
    """Choose to undo the add, as a user at a prompt may."""
    return TaskFailureChoice.UNDO


class Added(NamedTuple):
    """A project after docs was added to core and service.

    Attributes:
        project: The checkout after the add.
        outcome: What the add returned.
        start: The commit the checkout was at before the add.
        core_answers: What core's answers file recorded before the add.
    """

    project: Path
    outcome: AddOutcome
    start: str
    core_answers: str


@pytest.fixture(scope="module")
def added(family: Family, tmp_path_factory: pytest.TempPathFactory) -> Iterator[Added]:
    """Add docs, with the mkdocs generator, to a project of core and service."""
    work = tmp_path_factory.mktemp("add-docs")
    with temp_dir_inside(work):
        project = compose_locked_family(family, work, "service", BASE)
        start = head(project)
        core_answers = (project / ".copier-answers.core.yml").read_text("utf-8")
        outcome = LayerAdder().add(
            project, ask(family, "docs", "1.0.0", {"docs_generator": "mkdocs"})
        )
        yield Added(project, outcome, start, core_answers)


@pytest.mark.xdist_group("add-docs")
class TestAddedLayer:
    """Docs joins core and service as uncommitted changes."""

    def test_reports_the_layer_and_its_version(self, added: Added) -> None:
        assert (added.outcome.status, added.outcome.layer, added.outcome.version) == (
            AddStatus.ADDED,
            "docs",
            "1.0.0",
        )

    def test_leaves_the_checkout_at_its_commit(self, added: Added) -> None:
        assert head(added.project) == added.start

    def test_brings_the_files_back_uncommitted(self, added: Added) -> None:
        assert "mkdocs.yml" in status(added.project)

    def test_the_answers_file_records_the_layers_own_answer(self, added: Added) -> None:
        assert answers_file(added.project, "docs")["docs_generator"] == "mkdocs"

    def test_the_answers_file_records_the_release_it_was_added_at(
        self, added: Added
    ) -> None:
        assert answers_file(added.project, "docs")["_commit"] == "1.0.0"

    def test_the_answers_file_records_the_ancestors_answers(self, added: Added) -> None:
        keys = ("project_name", "author_name", "python_version")
        core = answers_file(added.project, "core")
        docs = answers_file(added.project, "docs")

        assert {k: docs[k] for k in keys} == {k: core[k] for k in keys}

    def test_leaves_the_ancestors_answers_files_alone(self, added: Added) -> None:
        recorded = (added.project / ".copier-answers.core.yml").read_text("utf-8")

        assert recorded == added.core_answers

    @pytest.mark.parametrize(
        ("path", "rendered"), [("mkdocs.yml", True), ("docs/conf.py", False)]
    )
    def test_renders_only_the_chosen_alternative(
        self, added: Added, path: str, rendered: bool
    ) -> None:
        assert (added.project / path).exists() is rendered

    def test_the_lock_lists_the_new_layer_last(self, added: Added) -> None:
        lock = read_lock(added.project)

        assert [(entry.name, str(entry.version)) for entry in lock.layers] == [
            ("core", "1.0.0"),
            ("service", "1.0.0"),
            ("docs", "1.0.0"),
        ]

    def test_the_lock_hashes_the_new_answers_file(self, added: Added) -> None:
        lock = read_lock(added.project)

        assert "docs" in (lock.copier_answers_file_hashes or {})

    def test_appends_one_success_record_without_a_prior_version(
        self, added: Added
    ) -> None:
        (record,) = read_migrations(added.project)

        assert (
            record.status,
            record.from_version,
            record.to_version,
            record.classification,
        ) == (MigrationStatus.SUCCESS, None, "docs@1.0.0", None)

    def test_does_not_run_the_ancestors_tasks_again(self, added: Added) -> None:
        assert not (added.project / ".core-task-marker").exists()


class Untouched(NamedTuple):
    """What a refused or failed add must leave as it found it."""

    head: str
    status: str
    lock: bytes | None
    migrations: bool


def snapshot(project: Path) -> Untouched:
    """Capture the checkout, the lock and whether a migration log exists."""
    lock = project / LOCK_FILE_NAME
    return Untouched(
        head(project),
        status(project),
        lock.read_bytes() if lock.exists() else None,
        (project / MIGRATIONS_FILE).exists(),
    )


def worktree_count(project: Path) -> int:
    """Return how many worktrees git registers for the project."""
    return git(project, "worktree", "list", "--porcelain").count("worktree ")


@pytest.fixture
def project(family: Family, tmp_path: Path) -> Path:
    """Compose core and service, lock them and commit."""
    return compose_locked_family(family, tmp_path, "service", BASE)


@pytest.fixture
def staging_folders(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record the prefix of every temporary directory the run creates."""
    created: list[str] = []
    real = tempfile.mkdtemp

    def spy(
        suffix: str | None = None, prefix: str | None = None, dir: str | None = None
    ) -> str:
        created.append(prefix or "")
        return real(suffix, prefix, dir)

    monkeypatch.setattr(tempfile, "mkdtemp", spy)
    return created


class TestRefusals:
    """Each precondition fails with its error before a staging folder exists."""

    def test_the_spy_sees_the_staging_folder_of_a_valid_add(
        self, family: Family, project: Path, staging_folders: list[str]
    ) -> None:
        """Show the spy works: an add that passes every check stages."""
        LayerAdder().add(
            project, ask(family, "docs", "1.0.0", {"docs_generator": "mkdocs"})
        )

        assert STAGING_PREFIX in staging_folders

    def refuse(
        self,
        project: Path,
        request: AddRequest,
        error: type[BoilerplateError],
        staging_folders: list[str],
    ) -> BoilerplateError:
        """Run the add, expect `error`, and check nothing changed or was staged."""
        before = snapshot(project)

        with pytest.raises(error) as stop:
            LayerAdder().add(project, request)

        assert snapshot(project) == before
        assert worktree_count(project) == 1
        assert STAGING_PREFIX not in staging_folders
        return stop.value

    def test_an_unmanaged_project(
        self, family: Family, project: Path, staging_folders: list[str]
    ) -> None:
        (project / LOCK_FILE_NAME).unlink()
        commit_all(project, "unmanage")

        error = self.refuse(
            project, ask(family, "docs"), ProjectNotManagedError, staging_folders
        )

        assert str(error) == (
            "Project is not managed by Boilerplate. Use 'boilerplate adopt' first."
        )

    def test_a_dirty_tree(
        self, family: Family, project: Path, staging_folders: list[str]
    ) -> None:
        (project / "notes.txt").write_text("uncommittedBSN", encoding="utf-8")

        error = self.refuse(
            project, ask(family, "docs"), UpdateProjectNotReadyError, staging_folders
        )

        assert str(error) == (
            "Working tree has uncommitted changes. "
            "Commit or stash them before running boilerplate add."
        )

    def test_a_layer_already_in_the_project(
        self, family: Family, project: Path, staging_folders: list[str]
    ) -> None:
        error = self.refuse(
            project, ask(family, "service"), LayerAlreadyAddedError, staging_folders
        )

        assert str(error) == (
            "Template 'service' is already in this project. "
            "Use 'boilerplate update' instead."
        )

    def test_a_missing_ancestor(
        self, family: Family, tmp_path: Path, staging_folders: list[str]
    ) -> None:
        core_only = compose_locked_family(family, tmp_path, "core", {"core": "1.0.0"})

        error = self.refuse(
            core_only, ask(family, "app"), AddAncestorsMissingError, staging_folders
        )

        assert isinstance(error, AddAncestorsMissingError)
        assert error.layers == ("service", "docs")

    def test_an_ancestor_too_old(
        self, project: Path, staging_folders: list[str]
    ) -> None:
        pinned = build_layer(project.parent, "pinned", extends="core@2.0.0")
        request = AddRequest(name="pinned", source=pinned.as_posix())

        error = self.refuse(project, request, AddAncestorVersionError, staging_folders)

        assert isinstance(error, AddAncestorVersionError)
        assert (error.ancestor, error.recorded, error.constraint) == (
            "core",
            "1.0.0",
            "core@2.0.0",
        )


class TestMidAddError:
    """An error after staging began leaves the checkout as it was."""

    def test_a_rejected_choice_leaves_the_project_untouched(
        self, family: Family, project: Path
    ) -> None:
        before = snapshot(project)

        with pytest.raises(ValueError, match="docs_generator"):
            LayerAdder().add(
                project, ask(family, "docs", "1.0.0", {"docs_generator": "hugo"})
            )

        assert snapshot(project) == before
        assert worktree_count(project) == 1


class CoreOnly:
    """Tests that start from core on its own, locked and committed."""

    @pytest.fixture
    def project(self, family: Family, tmp_path: Path) -> Path:
        """Compose core on its own, lock it and commit."""
        return compose_locked_family(family, tmp_path, "core", {"core": "1.0.0"})


class TestOwnTasks(CoreOnly):
    """The added layer's own tasks run once, after the copy back."""

    def test_the_layers_task_runs_once_under_the_copy_operation(
        self, project: Path
    ) -> None:
        build_layer(project.parent, "tasked", copier=OPERATION_TASK)

        LayerAdder().add(project, ask_built(project, "tasked"))

        assert lines(project / ".tasked-marker") == ["copy"]

    def test_the_ancestors_tasks_do_not_run_again(self, project: Path) -> None:
        build_layer(project.parent, "tasked", copier=OPERATION_TASK)

        LayerAdder().add(project, ask_built(project, "tasked"))

        assert not (project / ".core-task-marker").exists()

    def test_no_tasks_skips_the_layers_tasks(self, project: Path) -> None:
        build_layer(project.parent, "tasked", copier=OPERATION_TASK)

        LayerAdder().add(project, ask_built(project, "tasked", no_tasks=True))

        assert not (project / ".tasked-marker").exists()

    @pytest.fixture
    def secretive(self, project: Path) -> Path:
        """Add a layer whose task reads a secret answer; return the project."""
        build_layer(project.parent, "secretive", copier=SECRET_TASK)
        asked = AddRequest(
            name="secretive",
            source=(project.parent / "repos" / "secretive").as_posix(),
            supplied={"deploy_token": "s3cret"},
        )
        LayerAdder().add(project, asked)
        return project

    def test_a_secret_answer_reaches_the_task(self, secretive: Path) -> None:
        assert lines(secretive / ".token-marker") == ["s3cret"]

    def test_a_secret_answer_is_not_recorded_in_the_answers_file(
        self, secretive: Path
    ) -> None:
        assert "deploy_token" not in answers_file(secretive, "secretive")


class TestAFailedTask(CoreOnly):
    """A failed task is kept or undone as an update's is."""

    def test_a_caller_that_cannot_ask_keeps_the_files_and_raises(
        self, project: Path
    ) -> None:
        build_layer(project.parent, "failing", copier=FAILING_TASK)

        with pytest.raises(UpdateTaskFailedError) as stop:
            LayerAdder().add(project, ask_built(project, "failing"))

        assert stop.value.remediation is not None
        assert "Run it by hand" in stop.value.remediation

    def test_the_kept_add_still_writes_the_lock(self, project: Path) -> None:
        build_layer(project.parent, "failing", copier=FAILING_TASK)
        with pytest.raises(UpdateTaskFailedError):
            LayerAdder().add(project, ask_built(project, "failing"))

        assert [entry.name for entry in read_lock(project).layers] == [
            "core",
            "failing",
        ]

    def test_the_kept_add_is_recorded_as_failed(self, project: Path) -> None:
        build_layer(project.parent, "failing", copier=FAILING_TASK)
        with pytest.raises(UpdateTaskFailedError):
            LayerAdder().add(project, ask_built(project, "failing"))

        (record,) = read_migrations(project)

        assert (record.status, record.to_version) == (
            MigrationStatus.FAILED,
            "failing@1.0.0",
        )

    def test_undoing_returns_the_checkout_to_its_start(self, project: Path) -> None:
        build_layer(project.parent, "failing", copier=FAILING_TASK)
        before = (tree(project), (project / LOCK_FILE_NAME).read_bytes())

        outcome = LayerAdder(on_task_failure=undo).add(
            project, ask_built(project, "failing")
        )

        assert (
            outcome.status,
            tree(project),
            (project / LOCK_FILE_NAME).read_bytes(),
            git(project, "status", "--porcelain"),
            (project / MIGRATIONS_FILE).exists(),
        ) == (AddStatus.UNDONE, before[0], before[1], "", False)
