"""Warn of what changed outside Boilerplate since the lock was written."""

import hashlib
from importlib.metadata import version as installed_version
from pathlib import Path

from boilerplate.models import BoilerplateLock
from boilerplate.project_state.answers_file import answers_file_name


def answers_warnings(project: Path, lock: BoilerplateLock) -> list[str]:
    """Return a warning for each answers file edited since the lock was written.

    Each layer's answers file is hashed and compared with the hash the lock
    holds for it. The update goes on from the file as it is.

    Args:
        project: The project holding the answers files.
        lock: The project's lock.

    Returns:
        One warning per layer whose answers file no longer hashes as the lock
        recorded, in the lock's order.
    """
    recorded = lock.copier_answers_file_hashes or {}
    warnings: list[str] = []
    for entry in lock.layers:
        name = answers_file_name(entry.name)
        path = project / name
        if entry.name not in recorded or not path.is_file():
            continue
        if hashlib.sha256(path.read_bytes()).hexdigest() != recorded[entry.name]:
            warnings.append(
                f"Answer state for layer '{entry.name}' may have been externally "
                "modified since the last Boilerplate operation. The update will "
                f"use the current {name} contents."
            )
    return warnings


def copier_version_warnings(lock: BoilerplateLock) -> list[str]:
    """Return a warning when the installed Copier is not the one the lock records.

    Args:
        lock: The project's lock.

    Returns:
        A warning naming both versions; empty when they are the same.
    """
    installed = installed_version("copier")
    if installed == lock.copier_version:
        return []
    return [
        f"The project was last rendered with Copier {lock.copier_version}; "
        f"this update runs with Copier {installed}."
    ]
