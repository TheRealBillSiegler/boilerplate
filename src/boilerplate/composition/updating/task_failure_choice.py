"""What to do with an update whose task failed."""

from enum import StrEnum


class TaskFailureChoice(StrEnum):
    """The caller's answer when a task fails after the copy back.

    Attributes:
        KEEP: Keep the updated files, write the lock and report the failure.
        UNDO: Restore the tracked files and the index from the commit the
            run began at, and remove the untracked, non-ignored files the
            undo listed. Ignored files, ``.git`` and anything outside the
            project stay as they are.
    """

    KEEP = "keep"
    UNDO = "undo"
