"""Append an add's record to ``.boilerplate/migrations.yml``."""
# Spec: docs/design/06-project-lifecycle.md §Migration Records

from datetime import UTC, datetime
from pathlib import Path

from boilerplate.models import MigrationRecord, MigrationStatus
from boilerplate.project_state.migrations_file import (
    append_migration,
    next_migration_id,
    read_migrations,
)


class AddRecorder:
    """Appends the record of one add to the project's migration log.

    The record names the added layer in ``to_version`` and has no ``from_version``
    or classification: the layer had no prior version to compare with. The log
    is append-only, and an add appends one record, when it ends.
    """

    def __init__(self, project: Path) -> None:
        """Prepare to record an add to `project`.

        Args:
            project: The user's checkout, holding the log.
        """
        self._project = project

    def success(self, to_version: str) -> None:
        """Record an add that finished, after its lock was written.

        Args:
            to_version: The added layer's specifier, ``name@version``.
        """
        self._append(MigrationStatus.SUCCESS, to_version)

    def failed(self, to_version: str, error: str) -> None:
        """Record an add whose task failed after the copy back and was kept.

        Args:
            to_version: The added layer's specifier, ``name@version``.
            error: Why the add is recorded as failed.
        """
        self._append(MigrationStatus.FAILED, to_version, error=error)

    def _append(
        self, status: MigrationStatus, to_version: str, *, error: str | None = None
    ) -> None:
        """Append one record numbered after the log's last."""
        append_migration(
            self._project,
            MigrationRecord(
                id=next_migration_id(read_migrations(self._project)),
                from_version=None,
                to_version=to_version,
                timestamp=datetime.now(UTC),
                status=status,
                error=error,
            ),
        )
