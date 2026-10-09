"""The statuses a migration record can hold."""
# Spec: docs/design/02-data-models.md §MigrationRecord status state machine

from enum import StrEnum

__all__ = ["MigrationStatus"]


class MigrationStatus(StrEnum):
    """How an operation recorded in ``.boilerplate/migrations.yml`` stands.

    Exit codes: ``SUCCESS``, ``ADOPTED`` and ``CREATED`` are 0, ``CONFLICT`` is
    4 and ``FAILED`` is 1.
    """

    SUCCESS = "success"
    FAILED = "failed"
    CONFLICT = "conflict"
    ADOPTED = "adopted"
    CREATED = "created"
