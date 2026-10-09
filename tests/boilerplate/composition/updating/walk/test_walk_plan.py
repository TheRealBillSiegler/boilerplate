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
        layers=tuple(entry.name for entry in lock.layers),
        steps=(WalkStep(layer="core", release=release, views=views),),
        skipped=(),
        targets={
            "core": SerializableVersion("2.0.0"),
            "app": SerializableVersion("1.0.0"),
        },
        final_release=release,
        task_view=LayerView(questions={}, extensions=()),
        tasks=(),
        warnings=(),
    )


class TestWalkPlan:
    def test_the_final_layer_is_the_last_layer_of_the_lock(
        self,
        two_layer_lock: BoilerplateLock,
        core_release: LayerRelease,
        empty_views: UpdateViews,
    ) -> None:
        plan = _plan(two_layer_lock, core_release, empty_views)

        assert plan.final == "app"

    def test_the_final_layer_is_the_layer_added_last(
        self,
        added_layer_lock: BoilerplateLock,
        core_release: LayerRelease,
        empty_views: UpdateViews,
    ) -> None:
        """Run the tasks from the lock's last layer, as 04 §Safe Update says."""
        plan = _plan(added_layer_lock, core_release, empty_views)

        assert plan.final == "docs"

    def test_the_root_is_the_template_the_lock_names(
        self,
        two_layer_lock: BoilerplateLock,
        core_release: LayerRelease,
        empty_views: UpdateViews,
    ) -> None:
        plan = _plan(two_layer_lock, core_release, empty_views)

        assert plan.root == "app"

    def test_the_root_is_not_a_layer_added_after_it(
        self,
        added_layer_lock: BoilerplateLock,
        core_release: LayerRelease,
        empty_views: UpdateViews,
    ) -> None:
        """Record an update against the root template, not the layer added last."""
        plan = _plan(added_layer_lock, core_release, empty_views)

        assert plan.root == "app"
