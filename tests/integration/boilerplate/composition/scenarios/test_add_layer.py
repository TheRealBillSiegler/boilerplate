"""Adding layers to a project of the made-up template family.

``LayerAdder`` applies one more template to a project Boilerplate manages, the
way a by-hand ``copier copy`` with the layer's own answers file would. These
scenarios run whole adds against real Copier, git and tagged repositories: a
project that grows by two layers, the update that follows, a switch of the choice
a layer offers, a file the project owns and the prompts of an interactive add.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any, NamedTuple

import pytest

from boilerplate.composition.adding import (
    AddOutcome,
    AddRequest,
    AddStatus,
    LayerAdder,
)
from boilerplate.composition.updating.update_outcome import UpdateOutcome
from boilerplate.composition.updating.update_request import UpdateRequest
from boilerplate.composition.updating.update_status import UpdateStatus
from boilerplate.composition.updating.updater import Updater
from boilerplate.models import MigrationStatus
from boilerplate.project_state.lock_file import LOCK_FILE_NAME, read_lock
from boilerplate.project_state.migrations_file import read_migrations
from tests.boilerplate.templates.conftest import commit_all, git
from tests.integration.boilerplate.composition.family import Family
from tests.integration.boilerplate.composition.scenarios.builders import (
    AUTHOR,
    CLEAN,
    USER_LINE,
    add_user_line,
    answers_file,
    compose_locked_family,
    copy_project,
    lines,
    merge_state,
    tree,
)
from tests.integration.boilerplate.composition.scenarios.prompt_session import (
    PromptSession,
    drive_prompts,
)
from tests.integration.boilerplate.composition.temp_dir import temp_dir_inside

BASE = {"core": "1.0.0", "service": "1.0.0"}
AFTER = {"core": "1.1.0", "service": "1.2.0", "docs": "1.2.0", "ci": "1.1.0"}
GROWN = {"core": "1.0.0", "service": "1.0.0", "docs": "1.0.0", "ci": "1.0.0"}
LAYERS = ("core", "service", "docs", "ci")
WORKFLOW = ".github/workflows/ci.yml"
GITLAB_FILE = ".gitlab-ci.yml"


def ask(
    family: Family,
    name: str,
    ref: str,
    supplied: dict[str, Any] | None = None,
) -> AddRequest:
    """Build the request that adds family layer `name` at `ref`."""
    return AddRequest(
        name=name,
        source=family.repos[name].as_posix(),
        ref=ref,
        supplied=supplied or {},
    )


def add_and_commit(project: Path, request: AddRequest) -> None:
    """Add a layer and commit the result, as a user reviewing the add would."""
    outcome = LayerAdder().add(project, request)
    assert outcome.status is AddStatus.ADDED
    commit_all(project, f"add {request.name}")


def switch_provider(project: Path, provider: str) -> UpdateOutcome:
    """Run an update at the project's own releases that supplies `ci_provider`."""
    return Updater().update(
        project,
        UpdateRequest(targets=GROWN, supplied={"ci_provider": provider}),
    )


class Grown(NamedTuple):
    """A project of core and service that added docs, then ci.

    Attributes:
        project: The committed checkout after both adds.
        work: The scenario's working directory.
    """

    project: Path
    work: Path


class Updated(NamedTuple):
    """A grown project after an update, and what the update returned."""

    project: Path
    outcome: UpdateOutcome


@pytest.fixture(scope="module")
def grown(family: Family, tmp_path_factory: pytest.TempPathFactory) -> Iterator[Grown]:
    """Compose core and service, add docs with mkdocs, then ci with github."""
    work = tmp_path_factory.mktemp("add-later")
    with temp_dir_inside(work):
        project = compose_locked_family(
            family, work, "service", BASE, {"author_name": AUTHOR}
        )
        add_and_commit(
            project, ask(family, "docs", "1.0.0", {"docs_generator": "mkdocs"})
        )
        add_and_commit(project, ask(family, "ci", "1.0.0", {"ci_provider": "github"}))
        yield Grown(project, work)


@pytest.mark.xdist_group("add-later")
class TestAddingLater:
    """Docs and then ci join a project that began as core and service."""

    @pytest.mark.parametrize(
        ("layer", "own"),
        [("docs", {"docs_generator": "mkdocs"}), ("ci", {"ci_provider": "github"})],
    )
    def test_each_answers_file_records_the_layers_own_answers(
        self, grown: Grown, layer: str, own: dict[str, str]
    ) -> None:
        recorded = answers_file(grown.project, layer)

        assert {key: recorded[key] for key in own} == own

    @pytest.mark.parametrize("layer", ["docs", "ci"])
    def test_each_answers_file_records_its_ancestors_answers(
        self, grown: Grown, layer: str
    ) -> None:
        core = answers_file(grown.project, "core")
        recorded = answers_file(grown.project, layer)
        keys = ("project_name", "author_name", "python_version", "use_tests")

        assert {key: recorded[key] for key in keys} == {key: core[key] for key in keys}

    @pytest.mark.parametrize("layer", ["docs", "ci"])
    def test_each_answers_file_records_the_release_it_was_added_at(
        self, grown: Grown, layer: str
    ) -> None:
        assert answers_file(grown.project, layer)["_commit"] == "1.0.0"

    def test_the_lock_lists_the_layers_in_the_order_they_joined(
        self, grown: Grown
    ) -> None:
        lock = read_lock(grown.project)

        assert [entry.name for entry in lock.layers] == list(LAYERS)

    def test_the_log_holds_one_record_for_each_add(self, grown: Grown) -> None:
        records = read_migrations(grown.project)

        assert [(r.status, r.from_version, r.to_version) for r in records] == [
            (MigrationStatus.SUCCESS, None, "docs@1.0.0"),
            (MigrationStatus.SUCCESS, None, "ci@1.0.0"),
        ]

    @pytest.mark.parametrize(
        ("path", "rendered"),
        [
            ("mkdocs.yml", True),
            ("docs/conf.py", False),
            (WORKFLOW, True),
            (GITLAB_FILE, False),
        ],
    )
    def test_only_the_alternatives_chosen_are_rendered(
        self, grown: Grown, path: str, rendered: bool
    ) -> None:
        assert (path in tree(grown.project)) is rendered


class TestUpdateAfterAdds:
    """A project that grew by adds updates like one composed at once."""

    @pytest.fixture(scope="class")
    def updated(self, grown: Grown) -> Iterator[Updated]:
        """Update every layer of the grown project to a newer release."""
        project = copy_project(grown.project, grown.work / "updated" / "family-app")
        with temp_dir_inside(grown.work / "updated"):
            targets = {"core": "1.1.0", "docs": "1.2.0", "ci": "1.1.0"}
            yield Updated(
                project, Updater().update(project, UpdateRequest(targets=targets))
            )

    def test_the_update_completes(self, updated: Updated) -> None:
        assert updated.outcome.status is UpdateStatus.UPDATED

    def test_every_layer_updates_in_the_order_of_the_lock(
        self, updated: Updated
    ) -> None:
        assert updated.outcome.updated == LAYERS

    def test_every_answers_file_records_its_target(self, updated: Updated) -> None:
        recorded = {
            layer: answers_file(updated.project, layer)["_commit"] for layer in LAYERS
        }

        assert recorded == AFTER

    def test_the_lock_records_the_targets(self, updated: Updated) -> None:
        lock = read_lock(updated.project)

        assert {entry.name: str(entry.version) for entry in lock.layers} == AFTER

    def test_the_question_core_adds_reaches_the_layers_added_later(
        self, updated: Updated
    ) -> None:
        assert "license" in answers_file(updated.project, "ci")


class TestSwitchingTheChoice:
    """A layer's choice changes by an update that supplies the new answer."""

    @pytest.fixture(scope="class")
    def switched(self, grown: Grown) -> Iterator[Path]:
        """Switch ci from github to gitlab, as ``update --set`` would."""
        project = copy_project(grown.project, grown.work / "switched" / "family-app")
        with temp_dir_inside(grown.work / "switched"):
            switch_provider(project, "gitlab")
            yield project

    def test_the_old_alternatives_file_is_removed(self, switched: Path) -> None:
        assert not (switched / WORKFLOW).exists()

    def test_the_new_alternatives_file_is_added(self, switched: Path) -> None:
        assert (switched / GITLAB_FILE).is_file()

    def test_the_answers_file_records_the_new_choice(self, switched: Path) -> None:
        assert answers_file(switched, "ci")["ci_provider"] == "gitlab"

    def test_the_other_layers_are_as_they_were(
        self, grown: Grown, switched: Path
    ) -> None:
        before = tree(grown.project)
        after = tree(switched)
        changed = {
            path
            for path in before.keys() | after.keys()
            if before.get(path) != after.get(path)
        }

        assert changed - {WORKFLOW, GITLAB_FILE} <= {
            ".copier-answers.ci.yml",
            LOCK_FILE_NAME,
            ".boilerplate/migrations.yml",
            ".core-task-marker",
            ".core-operation-marker",
        }


class TestSwitchingAnEditedFile:
    """The user edited the file of the alternative that the switch drops.

    Observed with Copier 9.18: the update deletes the edited file as it does an
    untouched one, without a conflict or a ``.rej`` file. The deletion is an
    uncommitted change, so the edit stays in the commit the user made.
    """

    @pytest.fixture(scope="class")
    def edited(self, grown: Grown) -> Iterator[Updated]:
        """Edit the workflow, commit the edit, then switch ci to gitlab."""
        project = copy_project(grown.project, grown.work / "edited" / "family-app")
        with temp_dir_inside(grown.work / "edited"):
            add_user_line(project / WORKFLOW)
            yield Updated(project, switch_provider(project, "gitlab"))

    def test_the_update_completes_without_pausing(self, edited: Updated) -> None:
        assert (edited.outcome.status, edited.outcome.conflicts) == (
            UpdateStatus.UPDATED,
            (),
        )

    def test_the_edited_file_is_deleted(self, edited: Updated) -> None:
        assert not (edited.project / WORKFLOW).exists()

    def test_nothing_is_left_to_resolve(self, edited: Updated) -> None:
        assert merge_state(edited.project) == CLEAN

    def test_the_deletion_is_an_uncommitted_change(self, edited: Updated) -> None:
        assert f" D {WORKFLOW}" in git(edited.project, "status", "--porcelain")

    def test_the_edit_survives_in_the_commit_that_made_it(
        self, edited: Updated
    ) -> None:
        committed = git(edited.project, "show", f"HEAD:{WORKFLOW}")

        assert USER_LINE in committed

    def test_the_new_alternatives_file_is_added(self, edited: Updated) -> None:
        assert (edited.project / GITLAB_FILE).is_file()


class TestProjectOwnedFile:
    """A file the new layer lists in ``_skip_if_exists`` keeps the project's content."""

    @pytest.fixture(scope="class")
    def handbook(
        self, family: Family, tmp_path_factory: pytest.TempPathFactory
    ) -> Iterator[Path]:
        """Add handbook to a core project whose README the user has edited."""
        work = tmp_path_factory.mktemp("add-handbook")
        with temp_dir_inside(work):
            project = compose_locked_family(family, work, "core", {"core": "1.0.0"})
            add_user_line(project / "README.md")
            LayerAdder().add(project, ask(family, "handbook", "1.0.0"))
            yield project

    def test_the_listed_file_keeps_the_projects_content(self, handbook: Path) -> None:
        assert lines(handbook / "README.md")[-1] == USER_LINE

    def test_an_unlisted_file_another_layer_rendered_is_overwritten(
        self, handbook: Path
    ) -> None:
        assert lines(handbook / ".gitignore") == ["# handbook ignore list", ".idea/"]

    def test_the_overwrite_shows_in_the_uncommitted_diff(self, handbook: Path) -> None:
        assert ".gitignore" in git(handbook, "diff", "--name-only")

    def test_the_layers_other_files_are_added(self, handbook: Path) -> None:
        assert (handbook / "HANDBOOK.md").is_file()


class Prompted(NamedTuple):
    """A project after an interactive add, and the prompts the add put."""

    project: Path
    session: PromptSession[AddOutcome]


class TestPrompting:
    """An interactive add asks what no answers file of the project records."""

    @pytest.fixture
    def prompted(self, family: Family, tmp_path: Path) -> Prompted:
        """Add docs interactively, typing a site name and accepting the rest."""
        project = compose_locked_family(family, tmp_path, "service", BASE)
        request = AddRequest(
            name="docs",
            source=family.repos["docs"].as_posix(),
            ref="1.0.0",
            interactive=True,
        )
        session = drive_prompts(
            lambda: LayerAdder().add(project, request),
            typed={"docs_site_name": "Handbook"},
        )
        return Prompted(project, session)

    def test_the_run_finishes_without_error(self, prompted: Prompted) -> None:
        assert prompted.session.error is None

    def test_ancestors_recorded_answers_are_not_asked_again(
        self, prompted: Prompted
    ) -> None:
        """Ask the layer's own questions and core's secret, which no file records."""
        assert prompted.session.shown == [
            "api_token",
            "docs_generator",
            "docs_site_name",
        ]

    def test_the_typed_answer_is_recorded(self, prompted: Prompted) -> None:
        recorded = answers_file(prompted.project, "docs")

        assert recorded["docs_site_name"] == "Handbook"
