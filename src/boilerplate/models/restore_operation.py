"""The operations a restore marker can belong to."""
# Spec: docs/design/02-data-models.md §RestoreMarker

from enum import StrEnum

__all__ = ["RestoreOperation"]


class RestoreOperation(StrEnum):
    """The command whose copy back a restore marker brackets.

    Each value is the command's name, so a stop can name the command to rerun.
    """

    UPDATE = "update"
    ADD = "add"
