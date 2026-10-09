"""What one run of the update walk works on."""

from pathlib import Path

import pytest

from boilerplate.composition.updating.layer_release import LayerRelease
from boilerplate.composition.updating.update_request import UpdateRequest
from boilerplate.composition.updating.walk.walk_inputs import WalkInputs
from boilerplate.composition.updating.walk.walk_plan import WalkPlan
from boilerplate.composition.views import LayerView
from boilerplate.models import BoilerplateLock
from boilerplate.repository.release_checkouts import ReleaseCheckouts
from boilerplate.types import SerializableVersion


@pytest.fixture
def plan(two_layer_lock: BoilerplateLock, core_release: LayerRelease) -> WalkPlan:
    """Return the plan of an update that moves nothing."""
    return WalkPlan(
        lock=two_layer_lock,
        layers=("core", "app"),
        steps=(),
        skipped=(),
        targets={"core": SerializableVersion("1.0.0")},
        final_release=core_release,
        task_view=LayerView(questions={}, extensions=()),
        tasks=(),
        warnings=(),
    )


class TestWalkInputs:
    def test_holds_the_checkouts_it_is_given(
        self, tmp_path: Path, plan: WalkPlan
    ) -> None:
        with ReleaseCheckouts() as checkouts:
            inputs = WalkInputs(
                project=tmp_path,
                request=UpdateRequest(),
                plan=plan,
                checkouts=checkouts,
            )

            assert inputs.checkouts is checkouts
