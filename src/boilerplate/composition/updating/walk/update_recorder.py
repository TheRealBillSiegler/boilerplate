"""Append an update's records to ``.boilerplate/migrations.yml``."""
# Spec: docs/design/06-project-lifecycle.md §Migration Records

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

from boilerplate.models import BoilerplateLock, MigrationRecord, MigrationStatus
from boilerplate.project_state.migrations_file import (
    append_migration,
    next_migration_id,
    read_migrations,
)
from boilerplate.types.serializable_version import SerializableVersion


class UpdateRecorder:
    """Appends the records of one update to the project's migration log.

    Every record moves from the root template the lock being replaced names.
    Each is appended once, in its terminal status.
    """

    def __init__(self, project: Path, lock: BoilerplateLock) -> None:
        """Prepare to record an update that starts from `lock`.

        Args:
            project: The user's checkout, holding the log.
            lock: The lock the update starts from.
        """
        self._project = project
        self._from_version = lock.root_template

    def success(self, to_version: str) -> None:
        """Record an update that ran every layer, after its lock was written.

        Args:
            to_version: The root template specifier the update moved to.
        """
        self._append(MigrationStatus.SUCCESS, to_version)

    def failed(self, to_version: str, error: str) -> None:
        """Record an update whose task failed after the copy back.

        Args:
            to_version: The root template specifier the update moved to.
            error: Why the update is recorded as failed.
        """
        self._append(MigrationStatus.FAILED, to_version, error=error)

    def conflict(
        self,
        to_version: str,
        error: str,
        *,
        targets: Mapping[str, SerializableVersion],
        finished: Sequence[str],
    ) -> None:
        """Record a walk that paused on a conflict, for a rerun to resume from.

        Args:
            to_version: The root template specifier the update is moving to.
            error: What conflicted.
            targets: The version every layer was being updated to.
            finished: The layers the walk finished, in walk order, the layer
                that conflicted among them.
        """
        self._append(
            MigrationStatus.CONFLICT,
            to_version,
            error=error,
            targets={layer: str(version) for layer, version in targets.items()},
            finished=tuple(finished),
        )

    def _append(
        self,
        status: MigrationStatus,
        to_version: str,
        *,
        error: str | None = None,
        targets: Mapping[str, str] | None = None,
        finished: tuple[str, ...] | None = None,
    ) -> None:
        """Append one record numbered after the log's last."""
        append_migration(
            self._project,
            MigrationRecord(
                id=next_migration_id(read_migrations(self._project)),
                from_version=self._from_version,
                to_version=to_version,
                timestamp=datetime.now(UTC),
                status=status,
                error=error,
                targets=targets,
                finished=finished,
            ),
        )
