"""One layer's step of an update walk."""

from dataclasses import dataclass

from boilerplate.composition.updating.layer_release import LayerRelease
from boilerplate.composition.updating.update_views import UpdateViews


@dataclass(frozen=True)
class WalkStep:
    """What the walk needs to update one layer.

    Attributes:
        layer: The layer to update.
        release: The layer's source and the ref of its target release.
        views: The layer's views at the recorded releases and at the targets.
    """

    layer: str
    release: LayerRelease
    views: UpdateViews
