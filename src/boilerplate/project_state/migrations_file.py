"""Read and append the ``.boilerplate/migrations.yml`` audit log."""
# Spec: docs/design/06-project-lifecycle.md §Migration Records

import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Final

import yaml
from pydantic import TypeAdapter, ValidationError

from boilerplate.common.yaml_loading import load_yaml
from boilerplate.models import MigrationRecord
from boilerplate.project_state.atomic_write import write_text_atomically

__all__ = [
    "MIGRATIONS_FILE",
    "append_migration",
    "next_migration_id",
    "read_migrations",
]

MIGRATIONS_FILE: Final = Path(".boilerplate") / "migrations.yml"
"""The log's path relative to the project root."""

_logger = logging.getLogger(__name__)
_RECORDS = TypeAdapter(tuple[MigrationRecord, ...])


def read_migrations(project: Path) -> tuple[MigrationRecord, ...]:
    """Read the project's migration records, oldest first.

    A log that cannot be parsed is advisory, not authoritative: the lock file
    is the source of truth, so a corrupted log reads as empty history after a
    warning, and the next appended record replaces the corrupted file.

    Args:
        project: The project root.

    Returns:
        The records in file order; empty when the file is missing, empty or
        corrupted.
    """
    path = project / MIGRATIONS_FILE
    try:
        raw = load_yaml(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return ()
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        _logger.warning("Treating %s as empty history: %s", path, error)
        return ()
    if raw is None:
        return ()
    try:
        return _RECORDS.validate_python(raw)
    except ValidationError as error:
        _logger.warning("Treating %s as empty history: %s", path, error)
        return ()


def next_migration_id(records: Sequence[MigrationRecord]) -> str:
    """Return the id the record after `records` takes.

    Args:
        records: The history so far.

    Returns:
        The count of records plus one, as a string.

    Examples:
        >>> next_migration_id(())
        '1'
    """
    return str(len(records) + 1)


def append_migration(project: Path, record: MigrationRecord) -> None:
    """Append `record` to the project's log, leaving earlier records as they were.

    The new content is built in memory from the records already there and
    renamed over the file, so a crash leaves the old log or the new one.

    Args:
        project: The project root.
        record: The record to add; its id must be the next in sequence.

    Raises:
        ValueError: If the record's id is not the next one.
        OSError: If the file cannot be written; the old log is untouched.
    """
    existing = read_migrations(project)
    expected = next_migration_id(existing)
    if record.id != expected:
        raise ValueError(
            f"record id {record.id!r} is out of sequence; next id is {expected}"
        )
    text = yaml.safe_dump(
        [r.model_dump(mode="json") for r in (*existing, record)],
        sort_keys=True,
        default_flow_style=False,
        allow_unicode=True,
    )
    write_text_atomically(project / MIGRATIONS_FILE, text)
