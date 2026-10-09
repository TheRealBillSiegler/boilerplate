"""The update walk across the layers of the made-up template family.

``Updater`` walks a locked project layer by layer in a staging worktree and
brings the result back into the user's checkout. These scenarios run whole walks
against real Copier, git and tagged repositories: the diamond to newer releases
with a user's edit in it, the answers a step takes, a secret asked once, the
stops that come before any staging folder exists and an error in a later layer.
Pauses, resumes and tasks follow in the classes below.
"""

import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, NamedTuple

import pytest

from boilerplate.common.exceptions import (
    RecordedAnswerRejectedError,
    UpdateConflictPausedError,
    UpdateDowngradeError,
    UpdateLayerDriftError,
    UpdateProjectNotReadyError,
    UpdateTaskFailedError,
)
from boilerplate.composition.updating.failed_task import FailedTask
from boilerplate.composition.updating.task_failure_choice import TaskFailureChoice
from boilerplate.composition.updating.update_outcome import UpdateOutcome
from boilerplate.composition.updating.update_request import UpdateRequest
from boilerplate.composition.updating.update_status import UpdateStatus
from boilerplate.composition.updating.updater import Updater
from boilerplate.models import BoilerplateLock, MigrationStatus
from boilerplate.project_state.lock_builder import build_lock
from boilerplate.project_state.lock_file import read_lock, write_lock
from boilerplate.project_state.migrations_file import MIGRATIONS_FILE, read_migrations
from tests.boilerplate.templates.conftest import commit_all, git, rehome_layer
from tests.integration.boilerplate.composition.family import Family, build_family
from tests.integration.boilerplate.composition.scenarios.builders import (
    AUTHOR,
    USER_LINE,
    add_user_line,
    answers_file,
    compose_family,
    compose_locked_family,
    lines,
    tree,
    write,
)
from tests.integration.boilerplate.composition.scenarios.prompt_session import (
    drive_prompts,
)
from tests.integration.boilerplate.composition.temp_dir import temp_dir_inside

BASE = {"core": "1.0.0", "service": "1.0.0", "docs": "1.0.0", "app": "1.0.0"}
AFTER = {"core": "2.0.0", "service": "1.2.0", "docs": "1.2.0", "app": "1.1.0"}
LAYERS = ("core", "service", "docs", "app")


def head(project: Path) -> str:
    """Return the commit the checkout is at."""
    return git(project, "rev-parse", "HEAD").strip()


def request(
    targets: dict[str, str],
    supplied: dict[str, Any] | None = None,
    *,
    interactive: bool = False,
    no_tasks: bool = False,
) -> UpdateRequest:
    """Build an update request that moves the layers to `targets`."""
    return UpdateRequest(
        targets=targets,
        supplied=supplied or {},
        interactive=interactive,
        no_tasks=no_tasks,
    )


class Walked(NamedTuple):
    """A project after a walk, with what it started from.

    Attributes:
        project: The updated checkout.
        outcome: What the walk returned.
        start: The commit the checkout was at before the walk.
    """

    project: Path
    outcome: UpdateOutcome
    start: str


@pytest.fixture(scope="module")
def diamond(
    family: Family, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[Walked]:
    """Walk the diamond to newer releases with a user's edit in the README."""
    work = tmp_path_factory.mktemp("diamond-walk")
    with temp_dir_inside(work):
        project = compose_locked_family(
            family, work, "app", BASE, {"author_name": AUTHOR}
        )
        add_user_line(project / "SERVICE.md", prepend=True)
        start = head(project)
        outcome = Updater().update(project, request(AFTER))
        yield Walked(project, outcome, start)


@pytest.mark.xdist_group("update-walk-diamond")
class TestDiamondWalkToNewerReleases:
    """A user's edit survives a walk of every layer to its newer release."""

    def test_every_answers_file_records_its_target(self, diamond: Walked) -> None:
        """Record the target release in each layer's own answers file."""
        recorded = {
            layer: answers_file(diamond.project, layer)["_commit"] for layer in LAYERS
        }

        assert recorded == AFTER

    def test_the_lock_records_the_targets(self, diamond: Walked) -> None:
        """Write the lock the finished update describes."""
        lock = read_lock(diamond.project)

        assert {layer.name: str(layer.version) for layer in lock.layers} == AFTER

    def test_appends_one_success_record(self, diamond: Walked) -> None:
        """Log the update as complete, from the old root to the new."""
        records = read_migrations(diamond.project)

        assert [(r.status, r.from_version, r.to_version) for r in records] == [
            (MigrationStatus.SUCCESS, "app@1.0.0", "app@1.1.0")
        ]

    def test_the_users_edit_survives(self, diamond: Walked) -> None:
        """Keep the user's line where the user put it."""
        assert lines(diamond.project / "SERVICE.md")[0] == USER_LINE

    def test_the_template_change_is_merged_in(self, diamond: Walked) -> None:
        """Take service 1.2.0's new closing line, with core's migrated name."""
        assert lines(diamond.project / "SERVICE.md")[-1] == f"Maintained by {AUTHOR}."

    def test_the_checkout_stays_at_its_commit(self, diamond: Walked) -> None:
        """Commit nothing: the update is the user's to review."""
        assert head(diamond.project) == diamond.start

    def test_the_changes_are_uncommitted_working_changes(self, diamond: Walked) -> None:
        """Leave the merged guide as a change in the working tree."""
        status = git(diamond.project, "status", "--porcelain").splitlines()

        assert " M SERVICE.md" in status

    def test_the_outcome_lists_the_layers_in_walk_order(self, diamond: Walked) -> None:
        """Report every layer as updated, none skipped."""
        assert (diamond.outcome.updated, diamond.outcome.skipped) == (LAYERS, ())


SERVICE_BASE = {"core": "1.0.0", "service": "1.0.0"}
SERVICE_NEXT = {"core": "1.0.0", "service": "1.1.0"}
STAGING_PREFIX = "boilerplate-staging-"


def install_hook(project: Path, name: str, marker: Path) -> None:
    """Install a git hook that records its run by writing `marker`."""
    hook = project / ".git" / "hooks" / name
    hook.write_text(f'#!/bin/sh\necho ran > "{marker.as_posix()}"\n', encoding="utf-8")
    hook.chmod(0o755)


class ServiceWalk(NamedTuple):
    """A service project walked with hooks installed and an answer supplied.

    Attributes:
        project: The updated checkout.
        hooks_ran: The markers the project's hooks wrote, by hook name.
    """

    project: Path
    hooks_ran: dict[str, bool]


@pytest.fixture(scope="module")
def service_walk(
    family: Family, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[ServiceWalk]:
    """Walk core and service with a post-checkout and a pre-commit hook installed.

    Core stays at its release while service moves to the next one, and the
    walk supplies a new author for core's question.
    """
    work = tmp_path_factory.mktemp("service-walk")
    markers = {name: work / f"{name}.ran" for name in ("post-checkout", "pre-commit")}
    with temp_dir_inside(work):
        project = compose_locked_family(family, work, "service", SERVICE_BASE)
        for name, marker in markers.items():
            install_hook(project, name, marker)
        Updater().update(
            project, request(SERVICE_NEXT, supplied={"author_name": "Grace Hopper"})
        )
        yield ServiceWalk(project, {name: m.exists() for name, m in markers.items()})


@pytest.mark.xdist_group("update-walk-service")
class TestSuppliedAnswer:
    """A layer already at its target still runs, so a supplied answer reaches it."""

    def test_the_changed_answer_lands_in_the_layers_answers_file(
        self, service_walk: ServiceWalk
    ) -> None:
        """Record the supplied author in core, which did not move."""
        recorded = answers_file(service_walk.project, "core")

        assert (recorded["_commit"], recorded["author_name"]) == (
            "1.0.0",
            "Grace Hopper",
        )

    def test_the_changed_answer_is_rendered_into_the_layers_files(
        self, service_walk: ServiceWalk
    ) -> None:
        """Render the supplied author into core's README."""
        readme = lines(service_walk.project / "README.md")

        assert "A Python 3.13 project by Grace Hopper." in readme


@pytest.mark.xdist_group("update-walk-service")
class TestHooksNeverRun:
    """The project's own git hooks stay out of the staging."""

    @pytest.mark.parametrize("hook", ["post-checkout", "pre-commit"])
    def test_the_hook_did_not_run(self, service_walk: ServiceWalk, hook: str) -> None:
        """Create the worktree and commit each layer without firing it."""
        assert service_walk.hooks_ran[hook] is False


class TestSecretAskedOnce:
    """A secret question is asked at the first layer that holds it, and no later."""

    def test_the_prompt_for_a_secret_is_shown_once_across_the_walk(
        self, family: Family, tmp_path: Path
    ) -> None:
        """Carry the secret in memory from core's step into service's."""
        project = compose_locked_family(family, tmp_path, "service", SERVICE_BASE)

        session = drive_prompts(
            lambda: Updater().update(project, request(SERVICE_BASE, interactive=True))
        )

        assert (session.error, session.shown.count("api_token")) == (None, 1)


class TestStopsBeforeAnyStaging:
    """Preflight and the pre-walk checks stop an update before it creates a folder."""

    @pytest.fixture
    def staging_folders(self, monkeypatch: pytest.MonkeyPatch) -> list[str]:
        """Record the prefix of every temporary directory the run creates."""
        created: list[str] = []
        real = tempfile.mkdtemp

        def spy(
            suffix: str | None = None,
            prefix: str | None = None,
            dir: str | None = None,
        ) -> str:
            created.append(prefix or "")
            return real(suffix, prefix, dir)

        monkeypatch.setattr(tempfile, "mkdtemp", spy)
        return created

    def test_a_downgrade_is_rejected_first(
        self, family: Family, tmp_path: Path, staging_folders: list[str]
    ) -> None:
        """Refuse a target older than the layer's recorded release."""
        project = compose_locked_family(
            family, tmp_path, "service", {"core": "1.1.0", "service": "1.0.0"}
        )

        with pytest.raises(UpdateDowngradeError):
            Updater().update(project, request({"core": "1.0.0"}))

        assert STAGING_PREFIX not in staging_folders

    def test_a_layer_and_its_ancestor_that_drifted_are_refused_first(
        self, family: Family, tmp_path: Path, staging_folders: list[str]
    ) -> None:
        """Refuse a project where a hand-run update moved a layer and its ancestor."""
        project = compose_locked_family(family, tmp_path, "service", SERVICE_BASE)
        for layer in ("core", "service"):
            answers = project / f".copier-answers.{layer}.yml"
            text = answers.read_text(encoding="utf-8")
            write(answers, text.replace("_commit: 1.0.0", "_commit: 1.1.0"))
        commit_all(project, "hand-run updates")

        with pytest.raises(UpdateLayerDriftError):
            Updater().update(project, request(SERVICE_NEXT))

        assert STAGING_PREFIX not in staging_folders

    def test_a_dirty_tree_is_refused_first(
        self, family: Family, tmp_path: Path, staging_folders: list[str]
    ) -> None:
        """Refuse an uncommitted change, untracked files included."""
        project = compose_locked_family(family, tmp_path, "service", SERVICE_BASE)
        write(project / "scratch.txt", "not committed\n")

        with pytest.raises(UpdateProjectNotReadyError):
            Updater().update(project, request(SERVICE_NEXT))

        assert STAGING_PREFIX not in staging_folders


class ErrorMidWalk(NamedTuple):
    """A project before and after a walk that failed in its third layer.

    Attributes:
        project: The checkout.
        error: What the walk raised.
        before: The files and the lock before the walk.
        start: The commit before the walk.
        scratch: The temp directory the staging would be created under.
    """

    project: Path
    error: Exception
    before: dict[str, str]
    start: str
    scratch: Path


@pytest.fixture(scope="module")
def failed_walk(
    family: Family, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[ErrorMidWalk]:
    """Walk the diamond to docs 1.1.0, which rejects the recorded empty site name."""
    work = tmp_path_factory.mktemp("failed-walk")
    with temp_dir_inside(work) as scratch:
        project = compose_locked_family(
            family, work, "app", BASE, {"docs_site_name": ""}
        )
        before = tree(project)
        start = head(project)
        try:
            Updater().update(project, request({**BASE, "docs": "1.1.0"}))
        except RecordedAnswerRejectedError as error:
            yield ErrorMidWalk(project, error, before, start, scratch)
        else:
            pytest.fail("the walk was expected to be rejected")


@pytest.mark.xdist_group("update-walk-failed")
class TestAnErrorMidWalk:
    """A rejected recorded answer in a later layer undoes the whole walk."""

    def test_the_walk_stops_on_the_rejected_answer(
        self, failed_walk: ErrorMidWalk
    ) -> None:
        """Name the layer that rejected the answer."""
        assert isinstance(failed_walk.error, RecordedAnswerRejectedError)
        assert failed_walk.error.layer == "docs"

    def test_the_checkout_is_byte_identical(self, failed_walk: ErrorMidWalk) -> None:
        """Leave every file as it was, though two layers had already updated."""
        assert tree(failed_walk.project) == failed_walk.before

    def test_the_checkout_is_clean_and_at_its_commit(
        self, failed_walk: ErrorMidWalk
    ) -> None:
        """Leave no working change and move no commit."""
        assert (
            git(failed_walk.project, "status", "--porcelain"),
            head(failed_walk.project),
        ) == ("", failed_walk.start)

    def test_no_migration_record_is_written(self, failed_walk: ErrorMidWalk) -> None:
        """Log nothing: the user's checkout never changed."""
        assert not (failed_walk.project / MIGRATIONS_FILE).exists()

    def test_the_lock_is_the_one_it_was(self, failed_walk: ErrorMidWalk) -> None:
        """Keep the lock of the last complete operation."""
        lock = read_lock(failed_walk.project)

        assert {layer.name: str(layer.version) for layer in lock.layers} == BASE

    def test_no_staging_folder_or_worktree_is_left(
        self, failed_walk: ErrorMidWalk
    ) -> None:
        """Remove the worktree and its registration along with its folder."""
        leftovers = list(failed_walk.scratch.glob(f"{STAGING_PREFIX}*"))
        worktrees = git(failed_walk.project, "worktree", "list").splitlines()

        assert (leftovers, len(worktrees)) == ([], 1)


class TestACommitPastATag:
    """A recorded ``git describe`` string is a version Copier reads and compares."""

    def test_a_layer_recorded_past_its_tag_updates_end_to_end(
        self, tmp_path: Path
    ) -> None:
        """Walk from ``1.1.0-1-g<hash>`` to the next release and lock it."""
        private = build_family(tmp_path / "private")
        core = private.repos["core"]
        git(core, "switch", "-c", "past-tag", "1.1.0")
        git(core, "commit", "--allow-empty", "-m", "work after 1.1.0")
        described = git(core, "describe", "--tags", "--always").strip()
        git(core, "switch", "main")
        project = compose_family(
            private, tmp_path, "service", {"core": "1.1.0", "service": "1.0.0"}
        )
        rehome_layer(project, layer="core", source=core, commit=described)
        commit_all(project, "record core past its tag")
        order = ["core", "service"]
        write_lock(project, build_lock(project, order, boilerplate_version="0.0.0"))
        commit_all(project, "lock")

        Updater().update(project, request({"core": "2.0.0", "service": "1.2.0"}))

        lock = read_lock(project)
        assert {layer.name: str(layer.version) for layer in lock.layers} == {
            "core": "2.0.0",
            "service": "1.2.0",
        }


def publish_release(
    repo: Path, tag: str, edit: Callable[[Path], None] | None = None
) -> None:
    """Publish `tag` as a new release of the layer repository `repo`.

    The release carries the new version in ``boilerplate.yml``, which is all a
    release needs to be the latest one, and whatever `edit` changes in the
    repository's working tree.
    """
    manifest = repo / "boilerplate.yml"
    text = manifest.read_text(encoding="utf-8")
    current = next(
        line.split(":", 1)[1].strip()
        for line in text.splitlines()
        if line.startswith("version:")
    )
    write(manifest, text.replace(f"version: {current}", f"version: {tag}", 1))
    if edit is not None:
        edit(repo)
    commit_all(repo, f"release {tag}", tag)


def resolve_conflict(project: Path, relative: str) -> None:
    """Resolve the conflict in `relative` the way a user does: keep both sides."""
    path = project / relative
    kept = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if not line.startswith(("<<<<<<<", "=======", ">>>>>>>"))
    ]
    write(path, "\n".join(kept) + "\n")
    commit_all(project, "resolve the conflict")


class PausedWalk(NamedTuple):
    """A diamond walk that paused on a conflict in service's guide.

    Attributes:
        family: The private family the project was composed from.
        project: The checkout the pause left behind.
        error: The pause the walk raised.
        lock: The lock the pause left in place.
    """

    family: Family
    project: Path
    error: UpdateConflictPausedError
    lock: BoilerplateLock


@pytest.fixture(scope="module")
def paused(tmp_path_factory: pytest.TempPathFactory) -> Iterator[PausedWalk]:
    """Walk the diamond with a user line at the end of service's guide."""
    work = tmp_path_factory.mktemp("paused-walk")
    private = build_family(work / "private")
    with temp_dir_inside(work):
        project = compose_locked_family(private, work, "app", BASE)
        add_user_line(project / "SERVICE.md")
        lock = read_lock(project)
        try:
            Updater().update(project, request(AFTER))
        except UpdateConflictPausedError as error:
            yield PausedWalk(private, project, error, lock)
        else:
            pytest.fail("the walk was expected to pause")


@pytest.mark.xdist_group("update-walk-paused")
class TestConflictPause:
    """A release that clashes with a user edit pauses the walk at its layer."""

    def test_raises_the_pause_with_the_remediation(self, paused: PausedWalk) -> None:
        """Tell the user to resolve, commit and rerun, or to stash the update."""
        assert paused.error.remediation == (
            "Resolve conflicts and commit, then run 'boilerplate update' again. "
            "'git reset' and then 'git stash --include-untracked' set the partial update aside."
        )

    def test_raises_the_pause_under_its_registered_code(
        self, paused: PausedWalk
    ) -> None:
        """Carry the code design 07 registers for a conflict pause."""
        assert paused.error.error_code == "BP_UPDATE_CONFLICT_PAUSED"

    def test_the_message_names_the_layer_and_the_conflicted_file(
        self, paused: PausedWalk
    ) -> None:
        """Say where the walk stopped and what to resolve."""
        assert (
            str(paused.error) == "Layer 'service' left merge conflicts in: SERVICE.md."
        )

    def test_the_checkout_shows_the_file_unmerged(self, paused: PausedWalk) -> None:
        """Leave the conflicted guide as git reports an unmerged path."""
        status = git(paused.project, "status", "--porcelain").splitlines()

        assert "UU SERVICE.md" in status

    def test_the_finished_layers_are_brought_back(self, paused: PausedWalk) -> None:
        """Apply core's update, which finished before the pause."""
        assert answers_file(paused.project, "core")["_commit"] == "2.0.0"

    def test_layers_after_the_pause_are_left_alone(self, paused: PausedWalk) -> None:
        """Run no later layer over the unresolved tree."""
        assert answers_file(paused.project, "docs")["_commit"] == "1.0.0"

    def test_the_conflict_record_lists_the_targets(self, paused: PausedWalk) -> None:
        """Record where every layer was going, for the rerun."""
        (record,) = read_migrations(paused.project)

        assert (record.status, record.targets) == (MigrationStatus.CONFLICT, AFTER)

    def test_the_conflict_record_lists_the_finished_layers(
        self, paused: PausedWalk
    ) -> None:
        """Name the layers the walk completed, the conflicted one among them."""
        (record,) = read_migrations(paused.project)

        assert record.finished == ("core", "service")

    def test_no_lock_is_written(self, paused: PausedWalk) -> None:
        """Leave the lock of the last complete operation."""
        assert read_lock(paused.project) == paused.lock


@pytest.fixture(scope="module")
def resumed(paused: PausedWalk) -> Iterator[UpdateOutcome]:
    """Resolve the conflict, publish newer releases and run the update again."""
    resolve_conflict(paused.project, "SERVICE.md")
    for layer in ("service", "docs"):
        publish_release(paused.family.repos[layer], "1.3.0")
    with temp_dir_inside(paused.project.parent):
        yield Updater().update(paused.project)


@pytest.mark.xdist_group("update-walk-paused")
class TestResumeAfterAConflict:
    """The rerun finishes the paused update to the targets it recorded."""

    def test_skips_the_layers_the_paused_walk_finished(
        self, resumed: UpdateOutcome
    ) -> None:
        """Run only the layers after the conflicted one."""
        assert (resumed.skipped, resumed.updated) == (
            ("core", "service"),
            ("docs", "app"),
        )

    def test_updates_to_the_recorded_targets_not_the_latest(
        self, paused: PausedWalk, resumed: UpdateOutcome
    ) -> None:
        """Keep docs at 1.2.0 although 1.3.0 was published after the pause."""
        assert resumed.status is UpdateStatus.UPDATED
        assert answers_file(paused.project, "docs")["_commit"] == "1.2.0"

    def test_writes_the_lock_at_the_targets(
        self, paused: PausedWalk, resumed: UpdateOutcome
    ) -> None:
        """Record the finished update in the lock."""
        lock = read_lock(paused.project)

        assert resumed.status is UpdateStatus.UPDATED
        assert {layer.name: str(layer.version) for layer in lock.layers} == AFTER

    def test_appends_a_success_record_after_the_conflict(
        self, paused: PausedWalk, resumed: UpdateOutcome
    ) -> None:
        """Log the rerun as a new record, leaving the conflict record terminal."""
        records = read_migrations(paused.project)

        assert resumed.status is UpdateStatus.UPDATED
        assert [(r.id, r.status) for r in records] == [
            ("1", MigrationStatus.CONFLICT),
            ("2", MigrationStatus.SUCCESS),
        ]


@pytest.mark.xdist_group("update-walk-service")
class TestTasksAfterTheWalk:
    """The composition's tasks run once, against the finished project."""

    def test_core_runs_its_task_once_across_the_walk(
        self, service_walk: ServiceWalk
    ) -> None:
        """Append one line though two layers updated and each skipped its tasks."""
        marker = lines(service_walk.project / ".core-task-marker")

        assert marker == ["core task ran"]

    def test_the_task_runs_under_the_update_operation(
        self, service_walk: ServiceWalk
    ) -> None:
        """Give the task ``_copier_operation == "update"``."""
        marker = lines(service_walk.project / ".core-operation-marker")

        assert marker == ["update"]

    def test_the_tasks_run_in_the_users_checkout(
        self, service_walk: ServiceWalk
    ) -> None:
        """Leave the task's files as uncommitted additions."""
        status = git(service_walk.project, "status", "--porcelain").splitlines()

        assert "?? .core-task-marker" in status


class TestNoTasks:
    def test_no_tasks_skips_the_task_run(self, family: Family, tmp_path: Path) -> None:
        """Run no task when the request says so."""
        project = compose_locked_family(family, tmp_path, "service", SERVICE_BASE)

        Updater().update(project, request(SERVICE_NEXT, no_tasks=True))

        assert not (project / ".core-task-marker").exists()


FAILING_TASK = """  - command:
      - "{{ _copier_python }}"
      - -c
      - "raise SystemExit(7)"
"""
MARKER_TASK_END = "file=open('.core-operation-marker', 'a', encoding='utf-8'))\"\n"


def add_failing_task(repo: Path) -> None:
    """Add a task that exits non-zero to the core release being published."""
    config = repo / "copier.yml"
    text = config.read_text(encoding="utf-8")
    assert MARKER_TASK_END in text
    write(config, text.replace(MARKER_TASK_END, MARKER_TASK_END + FAILING_TASK, 1))


class FailedTaskWalk(NamedTuple):
    """A project whose update ran a task that failed.

    Attributes:
        project: The checkout.
        before: The files before the walk.
        start: The commit before the walk.
        lock: The lock before the walk.
        raised: What the walk raised, if it raised.
        outcome: What the walk returned, if it returned.
        asked: The failed tasks the walk offered to the handler.
    """

    project: Path
    before: dict[str, str]
    start: str
    lock: BoilerplateLock
    raised: Exception | None
    outcome: UpdateOutcome | None
    asked: list[FailedTask]


def walk_with_a_failing_task(
    work: Path, choice: TaskFailureChoice | None
) -> FailedTaskWalk:
    """Update core to a release whose task fails, answering the failure with `choice`.

    Args:
        work: A directory to build the family and the project in.
        choice: What the handler answers; ``None`` for the default handler, which
            keeps the files.

    Returns:
        The project and what the walk did.
    """
    private = build_family(work / "private")
    publish_release(private.repos["core"], "1.0.1", add_failing_task)
    asked: list[FailedTask] = []

    def handler(failed: FailedTask) -> TaskFailureChoice:
        asked.append(failed)
        assert choice is not None
        return choice

    with temp_dir_inside(work):
        project = compose_locked_family(private, work, "service", SERVICE_BASE)
        before, start, lock = tree(project), head(project), read_lock(project)
        updater = Updater() if choice is None else Updater(on_task_failure=handler)
        raised: Exception | None = None
        outcome: UpdateOutcome | None = None
        try:
            outcome = updater.update(
                project, request({"core": "1.0.1", "service": "1.0.0"})
            )
        except UpdateTaskFailedError as error:
            raised = error
    return FailedTaskWalk(project, before, start, lock, raised, outcome, asked)


@pytest.fixture(scope="module")
def kept_failure(tmp_path_factory: pytest.TempPathFactory) -> FailedTaskWalk:
    """Update with a failing task and the default handler, which keeps the files."""
    return walk_with_a_failing_task(tmp_path_factory.mktemp("kept-failure"), None)


@pytest.fixture(scope="module")
def undone_failure(tmp_path_factory: pytest.TempPathFactory) -> FailedTaskWalk:
    """Update with a failing task and a handler that undoes the update."""
    return walk_with_a_failing_task(
        tmp_path_factory.mktemp("undone-failure"), TaskFailureChoice.UNDO
    )


@pytest.mark.xdist_group("update-walk-kept-failure")
class TestAFailingTaskUnderKeep:
    """A caller that keeps the files gets the update, the lock and the failure."""

    def test_raises_naming_the_failed_task(self, kept_failure: FailedTaskWalk) -> None:
        """Name the command that exited non-zero."""
        error = kept_failure.raised

        assert isinstance(error, UpdateTaskFailedError)
        assert "SystemExit(7)" in error.task

    def test_says_how_to_rerun_the_task(self, kept_failure: FailedTaskWalk) -> None:
        """Point at the task and the project root."""
        error = kept_failure.raised

        assert isinstance(error, UpdateTaskFailedError)
        assert (error.remediation or "").startswith(
            "Run it by hand from the project root: "
        )

    def test_keeps_the_updated_files(self, kept_failure: FailedTaskWalk) -> None:
        """Leave the copied-back update in the checkout."""
        assert answers_file(kept_failure.project, "core")["_commit"] == "1.0.1"

    def test_writes_the_lock(self, kept_failure: FailedTaskWalk) -> None:
        """Record the update as applied, as the files are."""
        lock = read_lock(kept_failure.project)

        assert {layer.name: str(layer.version) for layer in lock.layers} == {
            "core": "1.0.1",
            "service": "1.0.0",
        }

    def test_appends_a_failed_record(self, kept_failure: FailedTaskWalk) -> None:
        """Log the update as failed, with the task in the message."""
        (record,) = read_migrations(kept_failure.project)

        assert (
            record.status,
            record.to_version,
            "SystemExit(7)" in (record.error or ""),
        ) == (
            MigrationStatus.FAILED,
            "service@1.0.0",
            True,
        )


@pytest.mark.xdist_group("update-walk-undone-failure")
class TestAFailingTaskUnderUndo:
    """A caller that undoes the update gets the checkout back as it was."""

    def test_reports_the_update_as_undone(self, undone_failure: FailedTaskWalk) -> None:
        """Return an outcome rather than raising."""
        assert undone_failure.outcome is not None
        assert undone_failure.outcome.status is UpdateStatus.UNDONE

    def test_the_handler_is_offered_the_failed_task_once(
        self, undone_failure: FailedTaskWalk
    ) -> None:
        """Ask the caller what to do with the one task that failed."""
        assert [("SystemExit(7)" in task.command) for task in undone_failure.asked] == [
            True
        ]

    def test_the_checkout_returns_to_its_starting_files(
        self, undone_failure: FailedTaskWalk
    ) -> None:
        """Restore every file and remove what the update and the tasks added."""
        assert tree(undone_failure.project) == undone_failure.before

    def test_the_checkout_is_clean_at_its_commit(
        self, undone_failure: FailedTaskWalk
    ) -> None:
        """Leave no working change, no staged change and no new commit."""
        assert (
            git(undone_failure.project, "status", "--porcelain"),
            head(undone_failure.project),
        ) == ("", undone_failure.start)

    def test_no_lock_is_written(self, undone_failure: FailedTaskWalk) -> None:
        """Leave the lock of the last complete operation."""
        assert read_lock(undone_failure.project) == undone_failure.lock

    def test_no_record_is_written(self, undone_failure: FailedTaskWalk) -> None:
        """Log nothing: the checkout is as it was."""
        assert not (undone_failure.project / MIGRATIONS_FILE).exists()
