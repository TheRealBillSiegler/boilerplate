"""What to do with an update whose task failed."""

from enum import StrEnum


class TaskFailureChoice(StrEnum):
    """The caller's answer when a task fails after the copy back.

    Attributes:
        KEEP: Keep the updated files, write the lock and report the failure.
        UNDO: Return the checkout to its state before the update.
    """

    KEEP = "keep"
    UNDO = "undo"
