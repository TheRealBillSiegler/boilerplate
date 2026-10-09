"""How an update walk ended."""

from enum import StrEnum


class UpdateStatus(StrEnum):
    """The way a walk that raised nothing ended.

    Attributes:
        UPDATED: Every layer ran, the files were copied back and the lock written.
        PAUSED: A layer's update left conflicts; the checkout holds the partial
            update and no lock was written.
        UNDONE: A task failed after the copy back and the caller chose to undo
            the update; the tracked files and the index are back at the
            starting commit, the untracked, non-ignored files the undo listed
            are removed, and no lock was written. Ignored files, ``.git`` and
            anything outside the project are left as they were; the outcome's
            ``ignored_left`` names the ignored entries the tasks made.
    """

    UPDATED = "updated"
    PAUSED = "paused"
    UNDONE = "undone"
