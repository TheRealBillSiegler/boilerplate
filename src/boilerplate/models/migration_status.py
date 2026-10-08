"""The statuses a migration record can hold."""
# Spec: docs/design/02-data-models.md §MigrationRecord status state machine

from enum import StrEnum

__all__ = ["MigrationStatus"]


class MigrationStatus(StrEnum):
    """How an operation recorded in ``.boilerplate/migrations.yml`` stands.

    ``IN_PROGRESS`` is transient: the copy back from the staging worktree has
    started and the record awaits an in-place update to a terminal value.
    Exit codes: ``SUCCESS``, ``ADOPTED`` and ``CREATED`` are 0, ``CONFLICT`` is
    4 and ``FAILED`` is 1.
    """

    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    CONFLICT = "conflict"
    ADOPTED = "adopted"
    CREATED = "created"
