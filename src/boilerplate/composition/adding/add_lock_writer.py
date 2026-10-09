"""Write the lock an add ends with."""
# Spec: docs/design/06-project-lifecycle.md §Add pipeline

from pathlib import Path

from boilerplate.composition.adding.add_plan import AddPlan
from boilerplate.models import BoilerplateLock
from boilerplate.project_state.lock_builder import build_lock, mark_added
from boilerplate.project_state.lock_file import write_lock
from boilerplate.repository.release_checkouts import ReleaseCheckouts


def write_add_lock(
    project: Path,
    plan: AddPlan,
    boilerplate_version: str,
    checkouts: ReleaseCheckouts | None = None,
) -> BoilerplateLock:
    """Write the lock the answers files describe, the new layer last.

    The new layer is written with the ``add`` origin and the layers already in the
    lock keep theirs. Call it only once the add's files are in the checkout: the
    lock records the last complete operation.

    Args:
        project: The user's checkout, holding the new layer's answers file.
        plan: The add's plan, whose lock is the one being replaced (the project
            keeps its creation time) and whose layers are the new lock's order.
        boilerplate_version: The version of the tool writing the lock.
        checkouts: Release checkouts the add already holds, so the lock does not
            clone the releases again.

    Returns:
        The lock that was written.

    Raises:
        OSError: If the lock cannot be written; the previous lock is untouched.
    """
    lock = mark_added(
        build_lock(
            project,
            plan.layers,
            boilerplate_version=boilerplate_version,
            previous=plan.lock,
            checkouts=checkouts,
        ),
        plan.layer,
    )
    write_lock(project, lock)
    return lock
