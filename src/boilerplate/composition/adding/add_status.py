"""How an add ended."""

from enum import StrEnum


class AddStatus(StrEnum):
    """The way an add that raised nothing ended.

    Attributes:
        ADDED: The layer's files were copied back and the lock written.
        UNDONE: A task failed after the copy back and the caller chose to undo
            the add; the checkout is as it was and no lock was written.
    """

    ADDED = "added"
    UNDONE = "undone"
