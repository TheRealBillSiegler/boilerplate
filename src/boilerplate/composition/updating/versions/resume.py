"""Decide whether an update resumes a paused walk."""
# Spec: docs/design/04-composition-engine.md §Safe Update

from collections.abc import Mapping, Sequence

from boilerplate.common.exceptions import UpdateTargetMismatchError
from boilerplate.composition.updating.versions.layer_versions import LayerVersions
from boilerplate.composition.updating.versions.resume_plan import ResumePlan
from boilerplate.models import MigrationRecord
from boilerplate.types.serializable_version import SerializableVersion

__all__ = ["plan_resume"]


def plan_resume(
    layers: Sequence[LayerVersions],
    last_record: MigrationRecord | None,
    explicit_targets: Mapping[str, SerializableVersion] | None = None,
) -> ResumePlan | None:
    """Return the plan that resumes a paused update, or ``None`` to plan afresh.

    A ``conflict`` record binds only while the finished layers' answers files
    still record the targets it names; once the partial update is set aside,
    or a finished layer is updated again by hand, it no longer binds. Versions
    alone cannot tell a finished layer from an unfinished one, because a layer
    whose own version did not move still ran in the paused walk, so the record
    names the finished layers.

    Args:
        layers: Every layer of the project, in the lock's walk order.
        last_record: The last record of ``.boilerplate/migrations.yml``, if any.
        explicit_targets: The versions an explicit ``--target-version`` resolves
            to, keyed by layer; ``None`` when the user named none.

    Returns:
        The resume plan when the record binds, otherwise ``None``.

    Raises:
        UpdateTargetMismatchError: If the record binds and an explicit target
            differs from the one it records.
    """
    if (
        last_record is None
        or last_record.finished is None
        # Every conflict record has targets; this clause only narrows the type.
        or last_record.targets is None
    ):
        return None
    by_name = {layer.name: layer for layer in layers}
    if set(last_record.targets) != set(by_name):
        return None
    # The record's keys come back sorted; the walk, and the restore marker
    # built from these targets, keep the lock's order, root last.
    targets = {
        layer.name: SerializableVersion(last_record.targets[layer.name])
        for layer in layers
    }
    for name in last_record.finished:
        if name not in by_name or by_name[name].commit_version != targets[name]:
            return None
    requested = explicit_targets or {}
    mismatched = [
        name for name, wanted in requested.items() if targets.get(name) != wanted
    ]
    if mismatched:
        detail = "; ".join(
            f"{name}: requested {requested[name]}, recorded {targets.get(name)}"
            for name in mismatched
        )
        raise UpdateTargetMismatchError(
            f"The paused update targets other versions than requested ({detail}).",
            layers=mismatched,
        )
    finished = tuple(last_record.finished)
    return ResumePlan(
        finished=finished,
        remaining=tuple(layer.name for layer in layers if layer.name not in finished),
        targets=targets,
    )
