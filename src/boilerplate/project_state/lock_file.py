"""Read and write ``boilerplate.lock`` in a project root."""
# Spec: docs/design/06-project-lifecycle.md §Lock File Recovery
# Spec: docs/design/06-project-lifecycle.md §Lock File Versioning

import re
from pathlib import Path
from typing import Final

import yaml
from pydantic import ValidationError

from boilerplate.common.exceptions import (
    LockReadFailedError,
    LockSchemaUnsupportedError,
)
from boilerplate.common.yaml_loading import load_yaml
from boilerplate.models import LOCK_SCHEMA_MAJOR, LOCK_SCHEMA_VERSION, BoilerplateLock
from boilerplate.project_state.atomic_write import write_text_atomically

__all__ = ["LOCK_FILE_NAME", "read_lock", "write_lock"]

LOCK_FILE_NAME: Final = "boilerplate.lock"

_SCHEMA = re.compile(r"^boilerplate/lock@(\d+)(?:\.\d+)*$")


def _read_mapping(path: Path) -> dict[str, object]:
    """Parse `path` as a YAML mapping.

    Raises:
        LockReadFailedError: If the file is missing, unreadable, not YAML or
            not a mapping.
    """
    try:
        raw = load_yaml(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise LockReadFailedError(
            f"{LOCK_FILE_NAME} not found in {path.parent}.",
            remediation="Run 'boilerplate new' or 'boilerplate adopt' to create it.",
        ) from error
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise LockReadFailedError(
            f"{LOCK_FILE_NAME} cannot be parsed: {error}"
        ) from error
    if not isinstance(raw, dict):
        raise LockReadFailedError(f"{LOCK_FILE_NAME} is not a YAML mapping.")
    return {str(key): value for key, value in raw.items()}  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]


def _check_schema(raw: dict[str, object]) -> None:
    """Refuse an unrecognized or newer schema before any other field is read.

    Raises:
        LockReadFailedError: If ``schema_version`` is missing or is not a
            ``boilerplate/lock@<major>`` identifier of a supported major.
        LockSchemaUnsupportedError: If the major is newer than this tool
            supports.
    """
    schema = raw.get("schema_version")
    match = _SCHEMA.match(schema) if isinstance(schema, str) else None
    if match is None:
        raise LockReadFailedError(
            f"{LOCK_FILE_NAME} has an unrecognized schema_version: {schema!r}."
        )
    major = int(match.group(1))
    if major > LOCK_SCHEMA_MAJOR:
        raise LockSchemaUnsupportedError(
            f"{LOCK_FILE_NAME} uses schema {schema}; this tool supports "
            f"{LOCK_SCHEMA_VERSION}."
        )
    if major < LOCK_SCHEMA_MAJOR:
        raise LockReadFailedError(f"{LOCK_FILE_NAME} has an unknown schema {schema}.")


def read_lock(project: Path) -> BoilerplateLock:
    """Read the lock file of `project`, failing closed on anything untrusted.

    The schema is checked before any other field, so a lock from a newer
    generation is refused rather than partly parsed.

    Args:
        project: The project root holding ``boilerplate.lock``.

    Returns:
        The parsed lock.

    Raises:
        LockReadFailedError: If the file is missing, corrupted or does not
            match the lock schema.
        LockSchemaUnsupportedError: If the schema major is newer than this
            tool supports.
    """
    raw = _read_mapping(project / LOCK_FILE_NAME)
    _check_schema(raw)
    try:
        return BoilerplateLock.model_validate(raw)
    except ValidationError as error:
        raise LockReadFailedError(
            f"{LOCK_FILE_NAME} does not match the lock schema: {error}"
        ) from error


def write_lock(project: Path, lock: BoilerplateLock) -> None:
    """Write `lock` to the project root atomically, with keys in sorted order.

    Call this only after Copier has committed the render the lock describes;
    the lock records the last complete operation.

    Args:
        project: The project root.
        lock: The lock to write.

    Raises:
        OSError: If the file cannot be written; the previous lock is untouched.
    """
    text = yaml.safe_dump(
        lock.model_dump(mode="json"),
        sort_keys=True,
        default_flow_style=False,
        allow_unicode=True,
    )
    write_text_atomically(project / LOCK_FILE_NAME, text)
