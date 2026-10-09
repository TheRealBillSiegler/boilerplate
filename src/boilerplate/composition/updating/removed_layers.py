"""Decide which layers of a project the root's target version removes."""
# Spec: docs/design/06-project-lifecycle.md §Step 3: Build UpdatePlan

from collections.abc import Collection

from boilerplate.models import BoilerplateLock, JoinedVia

__all__ = ["removed_layers"]


def removed_layers(lock: BoilerplateLock, reached: Collection[str]) -> tuple[str, ...]:
    """Return the layers the root's target version no longer reaches.

    Only a layer that joined through ``extends`` can be removed this way. A layer
    ``add`` introduced is not governed by the root's target, so it stays in the
    lock until it is removed on purpose.

    Args:
        lock: The lock the update starts from.
        reached: The names of the layers the root's target version reaches
            through ``extends``, the root among them.

    Returns:
        The names of the removed layers, in the lock's order.
    """
    return tuple(
        entry.name
        for entry in lock.layers
        if entry.joined_via is JoinedVia.EXTENDS and entry.name not in reached
    )
