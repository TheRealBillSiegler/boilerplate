"""``LayerAdder`` adds one family layer to a locked project, or refuses to.

The expected behavior is design 05 §add and design 06 §Adding a layer: the
preconditions, their errors and remedies, the result as uncommitted changes, the
lock with the layer last, the migration record and the keep-or-undo handling of a
failed task.
"""

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
)
from boilerplate.composition.adding import (
    AddOutcome,
    AddRequest,
    AddStatus,
    LayerAdder,
)
from boilerplate.models import MigrationStatus
from boilerplate.project_state.lock_file import LOCK_FILE_NAME, read_lock
from boilerplate.project_state.migrations_file import MIGRATIONS_FILE, read_migrations
from tests.boilerplate.templates.conftest import commit_all, git
from tests.integration.boilerplate.composition.adding.layers import build_layer
from tests.integration.boilerplate.composition.family import Family
from tests.integration.boilerplate.composition.scenarios.builders import (
    answers_file,
    compose_locked_family,
)
from tests.integration.boilerplate.composition.temp_dir import temp_dir_inside

BASE = {"core": "1.0.0", "service": "1.0.0"}


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

    def test_renders_only_the_chosen_alternative(self, added: Added) -> None:
        assert (
            (added.project / "mkdocs.yml").is_file(),
            (added.project / "docs" / "conf.py").exists(),
        ) == (True, False)

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


class TestRefusals:
    """Each precondition fails with its error and leaves the project as it was."""

    def refuse(
        self, project: Path, request: AddRequest, error: type[BoilerplateError]
    ) -> BoilerplateError:
        """Run the add, expect `error`, and check nothing changed."""
        before = snapshot(project)

        with pytest.raises(error) as stop:
            LayerAdder().add(project, request)

        assert snapshot(project) == before
        assert worktree_count(project) == 1
        return stop.value

    def test_an_unmanaged_project(self, family: Family, project: Path) -> None:
        (project / LOCK_FILE_NAME).unlink()
        commit_all(project, "unmanage")

        error = self.refuse(project, ask(family, "docs"), ProjectNotManagedError)

        assert "boilerplate adopt" in str(error.remediation)

    def test_a_dirty_tree(self, family: Family, project: Path) -> None:
        (project / "notes.txt").write_text("uncommitted\n", encoding="utf-8")

        error = self.refuse(project, ask(family, "docs"), UpdateProjectNotReadyError)

        assert str(error) == (
            "Working tree has uncommitted changes. "
            "Commit or stash them before running boilerplate add."
        )

    def test_a_layer_already_in_the_project(
        self, family: Family, project: Path
    ) -> None:
        error = self.refuse(project, ask(family, "service"), LayerAlreadyAddedError)

        assert "boilerplate update" in str(error.remediation)

    def test_a_missing_ancestor(self, family: Family, tmp_path: Path) -> None:
        core_only = compose_locked_family(family, tmp_path, "core", {"core": "1.0.0"})

        error = self.refuse(core_only, ask(family, "app"), AddAncestorsMissingError)

        assert isinstance(error, AddAncestorsMissingError)
        assert error.layers == ("service", "docs")

    def test_an_ancestor_too_old(self, project: Path) -> None:
        pinned = build_layer(project.parent, "pinned", extends="core@2.0.0")
        request = AddRequest(name="pinned", source=pinned.as_posix())

        error = self.refuse(project, request, AddAncestorVersionError)

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
