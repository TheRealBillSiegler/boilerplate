"""The update walk across the layers of the made-up template family.

``Updater`` walks a locked project layer by layer in a staging worktree and
brings the result back into the user's checkout. These scenarios run whole walks
against real Copier, git and tagged repositories: the diamond to newer releases
with a user's edit in it, the answers a step takes, a secret asked once, the
stops that come before any staging folder exists and an error in a later layer.
Pauses, resumes and tasks follow in the classes below.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any, NamedTuple

import pytest

from boilerplate.composition.updating.update_outcome import UpdateOutcome
from boilerplate.composition.updating.update_request import UpdateRequest
from boilerplate.composition.updating.updater import Updater
from boilerplate.models import MigrationStatus
from boilerplate.project_state.lock_file import read_lock
from boilerplate.project_state.migrations_file import read_migrations
from tests.boilerplate.templates.conftest import git
from tests.integration.boilerplate.composition.family import Family
from tests.integration.boilerplate.composition.scenarios.builders import (
    AUTHOR,
    USER_LINE,
    add_user_line,
    answers_file,
    compose_locked_family,
    lines,
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
