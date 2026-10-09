"""How an add ended."""

from enum import StrEnum


class AddStatus(StrEnum):
    """The way an add that raised nothing ended.

    Attributes:
        ADDED: The layer's files were copied back and the lock written.
        UNDONE: A task failed after the copy back and the caller chose to undo
            the add; the tracked files and the index are back at the starting
            commit, the untracked, non-ignored files the undo listed are
            removed, and no lock was written. Ignored files, ``.git`` and
            anything outside the project are left as they were; the outcome's
            ``ignored_left`` names the ignored entries the tasks made.
    """

    ADDED = "added"
    UNDONE = "undone"
