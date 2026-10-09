"""Where a conflict paused a walk, for the restore marker to keep."""
# Spec: docs/design/02-data-models.md §RestoreMarker

from dataclasses import dataclass


@dataclass(frozen=True)
class WalkPause:
    """The layers of a walk a conflict paused, as the restore marker keeps them.

    Attributes:
        finished: The layers whose steps the walk finished, in walk order, the
            paused layer excluded.
        layer: The layer whose merge left conflict markers, which follows the
            finished layers.
    """

    finished: tuple[str, ...]
    layer: str
