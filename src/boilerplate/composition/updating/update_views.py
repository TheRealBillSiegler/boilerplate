"""The two views an update of one layer renders under."""

from typing import NamedTuple

from boilerplate.composition.views import LayerView


class UpdateViews(NamedTuple):
    """The views of the layer and its ancestors before and after an update.

    The two differ when an ancestor moves, even if the layer's own ref stays
    put, so a view keyed by the layer's ref cannot hold both.

    Attributes:
        old: The view at the recorded releases, for the old copy.
        target: The view at the target releases, for the in-place render and
            the new copy.
    """

    old: LayerView
    target: LayerView
