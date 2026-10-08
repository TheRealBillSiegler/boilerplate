"""Write the lock an update ends with."""
# Spec: docs/design/02-data-models.md §IntentJournal phase vocabularies

from pathlib import Path

from boilerplate.composition.staging import StagingWorktree
from boilerplate.models import BoilerplateLock
from boilerplate.project_state.lock_builder import build_lock
from boilerplate.project_state.lock_file import write_lock
from boilerplate.repository.release_checkouts import ReleaseCheckouts


def write_update_lock(
    project: Path,
    staging: StagingWorktree,
    previous: BoilerplateLock,
    boilerplate_version: str,
    checkouts: ReleaseCheckouts | None = None,
) -> BoilerplateLock:
    """Record the ``locking`` phase, then write the lock the answers files describe.

    The layers keep the order the previous lock lists, and the project keeps its
    creation time. Call it only once the update's files are in the checkout:
    the lock records the last complete update. If building the lock raises, the
    checkout stays updated, with the previous lock and no migration record.

    Args:
        project: The user's checkout, holding the updated answers files.
        staging: The active staging of the update, whose journal names the phase.
        previous: The lock being replaced.
        boilerplate_version: The version of the tool writing the lock.
        checkouts: Release checkouts the update already holds, so the lock does
            not clone the releases again.

    Returns:
        The lock that was written.

    Raises:
        ValueError: If a layer's answers file records no release that reads as a
            version.
        plumbum.commands.processes.ProcessExecutionError: If a layer's source
            cannot check its recorded release out.
        OSError: If the lock cannot be written; the previous lock is untouched.
    """
    staging.record_phase("locking")
    lock = build_lock(
        project,
        [layer.name for layer in previous.layers],
        boilerplate_version=boilerplate_version,
        previous=previous,
        checkouts=checkouts,
    )
    write_lock(project, lock)
    return lock
