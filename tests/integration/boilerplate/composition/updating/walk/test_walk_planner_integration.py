"""``plan_walk`` on a locked project of the made-up family, before any staging.

The plan is everything the walk decides without touching the checkout: the
targets, the layers to run with the release and views of each step, the tasks
to run afterwards and the stops that come before any staging folder exists.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest

from boilerplate.common.exceptions import (
    AnswersFileIncompleteError,
    UpdateDowngradeError,
    UpdateLayerDriftError,
    UpdateUnknownLayerError,
)
from boilerplate.composition.updating.update_request import UpdateRequest
from boilerplate.composition.updating.walk.walk_plan import WalkPlan
from boilerplate.composition.updating.walk.walk_planner import plan_walk
from boilerplate.project_state.answers_file import answers_file_name
from boilerplate.project_state.lock_file import read_lock
from boilerplate.repository.release_checkouts import ReleaseCheckouts
from tests.boilerplate.templates.conftest import commit_all
from tests.integration.boilerplate.composition.family import Family
from tests.integration.boilerplate.composition.scenarios.builders import (
    compose_locked_family,
    write,
)

pytestmark = [pytest.mark.scenario]

BASE = {"core": "1.0.0", "service": "1.0.0"}
CORE_MOVES = UpdateRequest(targets={"core": "1.1.0", "service": "1.0.0"})


class Planned:
    """A locked project of the family and the plan for a request against it."""

    def __init__(self, family: Family, work: Path, checkouts: ReleaseCheckouts) -> None:
        self.family = family
        self.work = work
        self.checkouts = checkouts

    def project(self, tags: dict[str, str]) -> Path:
        """Compose and lock the ``service`` project at `tags`."""
        return compose_locked_family(self.family, self.work, "service", tags)

    def plan(self, project: Path, request: UpdateRequest | None = None) -> WalkPlan:
        """Plan the walk of `project` for `request`."""
        return plan_walk(
            project,
            request or UpdateRequest(),
            read_lock(project),
            self.checkouts,
            self.work / "views",
        )


@pytest.fixture
def planned(family: Family, tmp_path: Path) -> Iterator[Planned]:
    """Return the planner harness, its checkouts removed after the test."""
    with ReleaseCheckouts() as checkouts:
        yield Planned(family, tmp_path, checkouts)


def target_versions(plan: WalkPlan) -> dict[str, str]:
    """Return the plan's targets as strings, keyed by layer."""
    return {layer: str(version) for layer, version in plan.targets.items()}


class TestTargets:
    def test_each_layer_defaults_to_its_latest_release(self, planned: Planned) -> None:
        """Take the latest tag of each source, as Copier does with no ref."""
        plan = planned.plan(planned.project({"core": "2.1.0", "service": "1.0.0"}))

        assert target_versions(plan) == {"core": "3.0.0", "service": "1.2.0"}

    def test_an_explicit_target_replaces_the_latest_for_its_layer(
        self, planned: Planned
    ) -> None:
        """Move only the named layer to the ref asked for."""
        plan = planned.plan(
            planned.project(BASE), UpdateRequest(targets={"service": "1.1.0"})
        )

        assert target_versions(plan) == {"core": "3.0.0", "service": "1.1.0"}

    def test_an_unknown_layer_in_the_targets_is_refused(self, planned: Planned) -> None:
        """Name the layer the project does not have."""
        project = planned.project(BASE)

        with pytest.raises(UpdateUnknownLayerError, match="docs") as caught:
            planned.plan(project, UpdateRequest(targets={"docs": "1.0.0"}))

        assert caught.value.layers == ("docs",)

    def test_the_refusal_lists_the_layers_the_project_has(
        self, planned: Planned
    ) -> None:
        """Tell the user which names a target may take."""
        project = planned.project(BASE)

        with pytest.raises(UpdateUnknownLayerError) as caught:
            planned.plan(project, UpdateRequest(targets={"docs": "1.0.0"}))

        assert (
            caught.value.remediation
            == "Name one of the project's layers: core, service."
        )


class TestSteps:
    def test_lists_every_layer_in_the_locks_order(self, planned: Planned) -> None:
        """Run each layer, ancestors first, though service's own ref stays put."""
        plan = planned.plan(planned.project(BASE), CORE_MOVES)

        assert [step.layer for step in plan.steps] == ["core", "service"]

    def test_a_step_moves_its_layer_to_the_target_ref_of_its_source(
        self, planned: Planned
    ) -> None:
        """Hand ``update_layer`` the layer's release."""
        plan = planned.plan(planned.project(BASE), CORE_MOVES)

        core = plan.steps[0].release
        assert (core.layer, str(core.source), core.ref) == (
            "core",
            planned.family.repos["core"].as_posix(),
            "1.1.0",
        )

    def test_a_steps_target_view_has_the_questions_an_ancestor_adds(
        self, planned: Planned
    ) -> None:
        """Ask core's new ``license`` under service's target view only."""
        plan = planned.plan(planned.project(BASE), CORE_MOVES)

        service = plan.steps[1].views
        assert (
            "license" in service.old.questions,
            "license" in service.target.questions,
        ) == (False, True)

    def test_the_task_view_is_the_roots_view_at_the_targets(
        self, planned: Planned
    ) -> None:
        """Render the post-walk tasks under the target releases' questions."""
        plan = planned.plan(planned.project(BASE), CORE_MOVES)

        assert "license" in plan.task_view.questions

    def test_the_tasks_are_the_composition_tasks_at_the_targets(
        self, planned: Planned
    ) -> None:
        """Collect core's two tasks once for the run after the walk."""
        plan = planned.plan(planned.project(BASE), CORE_MOVES)

        assert len(plan.tasks) == 2


class TestStopsBeforeStaging:
    def test_a_downgrade_is_rejected(self, planned: Planned) -> None:
        """Refuse a target older than the layer's recorded version."""
        project = planned.project({"core": "1.1.0", "service": "1.0.0"})

        with pytest.raises(UpdateDowngradeError):
            planned.plan(project, UpdateRequest(targets={"core": "1.0.0"}))

    def test_drift_of_a_layer_and_its_ancestor_is_refused(
        self, planned: Planned
    ) -> None:
        """Stop when a hand-run update left a layer and its ancestor off the lock."""
        project = planned.project(BASE)
        for layer in ("core", "service"):
            answers = project / answers_file_name(layer)
            text = answers.read_text(encoding="utf-8")
            write(answers, text.replace("_commit: 1.0.0", "_commit: 1.1.0"))
        commit_all(project, "hand-run updates")

        with pytest.raises(UpdateLayerDriftError):
            planned.plan(project)

    def test_a_trimmed_answers_file_is_refused(self, planned: Planned) -> None:
        """Stop when a layer's file lacks answers its scoped view asks for."""
        project = planned.project(BASE)
        answers = project / ".copier-answers.service.yml"
        recorded = answers.read_text(encoding="utf-8").splitlines()
        write(answers, "\n".join(line for line in recorded if line.startswith("_")))
        commit_all(project, "trimmed")

        with pytest.raises(AnswersFileIncompleteError):
            planned.plan(project)


class TestWarnings:
    def test_warns_of_an_answers_file_edited_since_the_lock(
        self, planned: Planned
    ) -> None:
        """Say which layer's answers file no longer hashes as the lock recorded."""
        project = planned.project(BASE)
        answers = project / ".copier-answers.core.yml"
        write(answers, answers.read_text(encoding="utf-8") + "# edited\n")
        commit_all(project, "edit answers")

        plan = planned.plan(project)

        assert [w for w in plan.warnings if "externally modified" in w] == [
            "Answer state for layer 'core' may have been externally modified since "
            "the last Boilerplate operation. The update will use the current "
            ".copier-answers.core.yml contents."
        ]

    def test_a_project_the_lock_describes_warns_of_nothing(
        self, planned: Planned
    ) -> None:
        """Stay quiet when the lock, the answers files and Copier all agree."""
        plan = planned.plan(planned.project(BASE))

        assert plan.warnings == ()
