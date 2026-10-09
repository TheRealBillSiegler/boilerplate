"""Resolve the versions an update runs at, before any layer runs."""
# Spec: docs/design/04-composition-engine.md §Safe Update

from collections.abc import Mapping, Sequence

from boilerplate.composition.updating.versions.downgrades import reject_downgrades
from boilerplate.composition.updating.versions.drift import check_drift
from boilerplate.composition.updating.versions.layer_versions import LayerVersions
from boilerplate.composition.updating.versions.old_copies import old_copy_for
from boilerplate.composition.updating.versions.resume_plan import ResumePlan
from boilerplate.composition.updating.versions.version_resolution import (
    VersionResolution,
)
from boilerplate.types.serializable_version import SerializableVersion

__all__ = ["resolve_versions"]


def resolve_versions(
    layers: Sequence[LayerVersions],
    planned_targets: Mapping[str, SerializableVersion],
    resume: ResumePlan | None,
) -> VersionResolution:
    """Decide the targets, the layers to run and each one's old copy.

    A resume plan decides the walk: it skips the finished layers and uses the
    recorded targets whatever `planned_targets` says, so a release published
    after the pause does not move them. Without one, the drift rules apply and
    every layer runs to its planned target. In both cases a downgrade stops the
    update before any layer runs.

    Args:
        layers: Every layer of the project, in the lock's walk order.
        planned_targets: The version each layer moves to if the update is
            fresh, keyed by name.
        resume: The plan that resumes a paused update (``plan_resume``), or
            ``None`` for a fresh one.

    Returns:
        The targets in force, the resume plan if any, the drift warnings and
        the old copy of each layer the walk runs.

    Raises:
        UpdateLayerDriftError: If a layer and an ancestor both disagree with the
            lock and there is no plan to resume.
        UpdateDowngradeError: If a target is older than a layer's recorded
            version, or a recorded ``_commit`` yields no version.
    """
    by_name = {layer.name: layer for layer in layers}
    if resume is None:
        warnings = check_drift(layers)
        targets: Mapping[str, SerializableVersion] = planned_targets
        to_run = list(layers)
    else:
        warnings = ()
        targets = resume.targets
        to_run = [by_name[name] for name in resume.remaining]
    reject_downgrades(to_run, targets)
    return VersionResolution(
        targets=targets,
        resume=resume,
        warnings=warnings,
        old_copies={layer.name: old_copy_for(layer, by_name) for layer in to_run},
    )
