"""How far a marked run got after its walk."""
# Spec: docs/design/02-data-models.md §RestoreMarker

from enum import StrEnum

__all__ = ["RestorePhase"]


class RestorePhase(StrEnum):
    """The step a run that wrote a restore marker is in.

    Attributes:
        COPY_BACK: From the moment the marker is written until the copy back
            ends.
        TASKS: While a complete update's tasks run.
        RECORDING: Until the record is appended; the lock and the record
            remain.
    """

    COPY_BACK = "copy_back"
    TASKS = "tasks"
    RECORDING = "recording"
