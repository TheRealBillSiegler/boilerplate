"""How an update walk ended."""

from enum import StrEnum


class UpdateStatus(StrEnum):
    """The way a walk that raised nothing ended.

    Attributes:
        UPDATED: Every layer ran, the files were copied back and the lock written.
        PAUSED: A layer's update left conflicts; the checkout holds the partial
            update and no lock was written.
        UNDONE: A task failed after the copy back and the caller chose to undo
            the update; the checkout is as it was and no lock was written.
    """

    UPDATED = "updated"
    PAUSED = "paused"
    UNDONE = "undone"
