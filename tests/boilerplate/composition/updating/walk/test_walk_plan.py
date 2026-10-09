"""Everything an update decides before it touches the checkout."""

from boilerplate.composition.updating.layer_release import LayerRelease
from boilerplate.composition.updating.update_views import UpdateViews
from boilerplate.composition.updating.walk.walk_plan import WalkPlan
from boilerplate.composition.updating.walk.walk_step import WalkStep
from boilerplate.composition.views import LayerView
from boilerplate.models import BoilerplateLock
from boilerplate.types import SerializableVersion


def _plan(lock: BoilerplateLock, release: LayerRelease, views: UpdateViews) -> WalkPlan:
    """Build the plan of an update that moves ``core`` and then ``app``."""
    return WalkPlan(
        lock=lock,
        layers=("core", "app"),
        steps=(WalkStep(layer="core", release=release, views=views),),
        skipped=(),
        targets={
            "core": SerializableVersion("2.0.0"),
            "app": SerializableVersion("1.0.0"),
        },
        root_release=release,
        task_view=LayerView(questions={}, extensions=()),
        tasks=(),
        warnings=(),
    )


class TestWalkPlan:
    def test_the_root_is_the_last_layer_of_the_lock(
        self,
        two_layer_lock: BoilerplateLock,
        core_release: LayerRelease,
        empty_views: UpdateViews,
    ) -> None:
        plan = _plan(two_layer_lock, core_release, empty_views)

        assert plan.root == "app"
