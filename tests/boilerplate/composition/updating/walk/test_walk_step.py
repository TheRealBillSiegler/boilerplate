"""One layer's step of an update walk."""

from boilerplate.composition.updating.layer_release import LayerRelease
from boilerplate.composition.updating.update_views import UpdateViews
from boilerplate.composition.updating.walk.walk_step import WalkStep


class TestWalkStep:
    def test_holds_the_layer_its_release_and_its_views(
        self, core_release: LayerRelease, empty_views: UpdateViews
    ) -> None:
        step = WalkStep(layer="core", release=core_release, views=empty_views)

        assert (step.layer, step.release, step.views) == (
            "core",
            core_release,
            empty_views,
        )
