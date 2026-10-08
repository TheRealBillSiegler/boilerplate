"""How large an update's version step is."""
# Spec: docs/design/02-data-models.md §UpdatePlan

from enum import StrEnum

__all__ = ["ChangeClassification"]


class ChangeClassification(StrEnum):
    """The size of an update, the highest bump across its layers."""

    PATCH = "PATCH"
    MINOR = "MINOR"
    MAJOR = "MAJOR"
