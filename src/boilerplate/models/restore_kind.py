"""Whether the walk a restore marker brackets finished every layer."""
# Spec: docs/design/02-data-models.md §RestoreMarker

from enum import StrEnum

__all__ = ["RestoreKind"]


class RestoreKind(StrEnum):
    """What the copy back of a marked run brings into the checkout.

    Attributes:
        COMPLETE: A walk that finished every layer.
        PAUSED: A walk a conflict paused; it runs no tasks and writes no lock.
    """

    COMPLETE = "complete"
    PAUSED = "paused"
