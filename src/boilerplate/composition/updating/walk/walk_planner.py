"""Plan an update walk: every check that comes before staging."""
# Spec: docs/design/06-project-lifecycle.md §Update Pipeline

from collections.abc import Mapping, Sequence
from pathlib import Path

from boilerplate.composition.updating.answers_completeness import (
    check_answers_complete,
)
from boilerplate.composition.updating.layer_release import LayerRelease
from boilerplate.composition.updating.recorded_answers import (
    read_recorded_answers_by_layer,
)
from boilerplate.composition.updating.release_ref import ReleaseRef
from boilerplate.composition.updating.release_views import ReleaseViews
from boilerplate.composition.updating.update_request import UpdateRequest
from boilerplate.composition.updating.versions import (
    LayerVersions,
    ResumePlan,
    VersionResolution,
    plan_resume,
    read_layer_versions,
    resolve_versions,
)
from boilerplate.composition.updating.walk.answers_warnings import (
    answers_warnings,
    copier_version_warnings,
)
from boilerplate.composition.updating.walk.layer_sources import read_layer_sources
from boilerplate.composition.updating.walk.lock_releases import lock_releases
from boilerplate.composition.updating.walk.target_releases import (
    Releases,
    Versions,
    named_releases,
    recorded_releases,
)
from boilerplate.composition.updating.walk.walk_plan import WalkPlan
from boilerplate.composition.updating.walk.walk_step import WalkStep
from boilerplate.models import BoilerplateLock
from boilerplate.project_state.migrations_file import read_migrations
from boilerplate.repository.release_checkouts import ReleaseCheckouts

__all__ = ["plan_walk"]


def plan_walk(
    project: Path,
    request: UpdateRequest,
    lock: BoilerplateLock,
    checkouts: ReleaseCheckouts,
    workdir: Path,
) -> WalkPlan:
    """Decide what an update of `project` does, without changing anything.

    Reads each layer's answers file and the lock, finds the targets (the latest
    release of each layer, an explicit ref, or the targets a paused update
    recorded), and runs the checks that stop an update before any staging
    folder exists: downgrades, drift and incomplete answers files. For each
    layer the walk runs, it builds the views of the old copy and of the target.

    Args:
        project: The project, a git repository root.
        request: What the user asked of the update.
        lock: The project's lock.
        checkouts: The release checkouts the views read; they must outlive the
            plan, since the views hold paths into them.
        workdir: A directory to assemble the templates directories in; it must
            outlive the plan too.

    Returns:
        The plan.

    Raises:
        ValueError: If the request names a layer the project does not have.
        UpdateTargetMismatchError: If an explicit target differs from a paused
            update's recorded one.
        UpdateLayerDriftError: If a layer and an ancestor both disagree with the
            lock and no paused update binds.
        UpdateDowngradeError: If a target is older than a layer's recorded
            version.
        AnswersFileIncompleteError: If a layer's answers file lacks answers its
            old view asks for.
    """
    layers = tuple(entry.name for entry in lock.layers)
    unknown = sorted(set(request.targets) - set(layers))
    if unknown:
        raise ValueError(f"unknown layer(s) in the targets: {', '.join(unknown)}")
    root = layers[-1]
    sources = read_layer_sources(project, lock)
    at_lock = lock_releases(lock, sources)
    views = ReleaseViews(checkouts, root=root, workdir=workdir)
    layer_versions = read_layer_versions(
        project, lock, views.ancestors(at_lock), checkouts
    )
    records = read_migrations(project)
    last_record = records[-1] if records else None
    explicit_releases, explicit_versions = named_releases(
        sources, dict(request.targets), checkouts
    )
    resume = plan_resume(layer_versions, last_record, explicit_versions or None)
    resolution, target_releases = (
        _fresh_targets(
            sources, checkouts, layer_versions, explicit_releases, explicit_versions
        )
        if resume is None
        else _resumed_targets(sources, layer_versions, resume)
    )

    steps = tuple(
        _step(
            layer,
            # The old copy renders the layer at its own recorded _commit and every
            # other layer at the release the lock records.
            {**at_lock, layer: ReleaseRef(source=sources[layer], ref=old.commit)},
            target_releases,
            views,
        )
        for layer, old in resolution.old_copies.items()
    )
    check_answers_complete(
        {step.layer: step.views.old for step in steps},
        read_recorded_answers_by_layer(project),
    )
    return WalkPlan(
        lock=lock,
        layers=layers,
        steps=steps,
        skipped=resume.finished if resume is not None else (),
        targets=dict(resolution.targets),
        root_release=LayerRelease.from_release(root, target_releases[root]),
        task_view=views.step_view(root, target_releases),
        tasks=tuple(views.tasks(target_releases)),
        warnings=(
            *answers_warnings(project, lock),
            *copier_version_warnings(lock),
            *(warning.message for warning in resolution.warnings),
        ),
    )


def _fresh_targets(
    sources: Mapping[str, str],
    checkouts: ReleaseCheckouts,
    layer_versions: Sequence[LayerVersions],
    explicit_releases: Releases,
    explicit_versions: Versions,
) -> tuple[VersionResolution, Releases]:
    """Resolve a fresh update: the named layers to their targets, the rest to latest.

    Args:
        sources: The template source of every layer, keyed by layer name.
        checkouts: The release checkouts of the update.
        layer_versions: What the lock and the answers files say about every
            layer, in the lock's order.
        explicit_releases: The releases the request's named layers resolve to.
        explicit_versions: The versions the request's named layers resolve to.

    Returns:
        The resolution of the versions and the release every layer moves to.
    """
    layers = [layer.name for layer in layer_versions]
    latest = {layer: None for layer in layers if layer not in explicit_releases}
    latest_releases, latest_versions = named_releases(sources, latest, checkouts)
    planned = explicit_versions | latest_versions
    resolution = resolve_versions(
        layer_versions, {layer: planned[layer] for layer in layers}, None
    )
    releases = explicit_releases | latest_releases
    return resolution, {layer: releases[layer] for layer in layers}


def _resumed_targets(
    sources: Mapping[str, str],
    layer_versions: Sequence[LayerVersions],
    resume: ResumePlan,
) -> tuple[VersionResolution, Releases]:
    """Resolve a resumed update: every layer to the target the paused update recorded.

    Args:
        sources: The template source of every layer, keyed by layer name.
        layer_versions: What the lock and the answers files say about each layer.
        resume: The plan that resumes the paused update.

    Returns:
        The resolution of the versions and the release every layer moves to.

    Raises:
        TemplateNotFoundError: If a source has no tag for a recorded target.
    """
    resolution = resolve_versions(layer_versions, {}, resume)
    return resolution, recorded_releases(sources, resolution.targets)


def _step(
    layer: str,
    old: Mapping[str, ReleaseRef],
    target_releases: Mapping[str, ReleaseRef],
    views: ReleaseViews,
) -> WalkStep:
    """Build the step that updates `layer` from the `old` releases to the targets."""
    return WalkStep(
        layer=layer,
        release=LayerRelease.from_release(layer, target_releases[layer]),
        views=views.update_views(layer, old=old, target=target_releases),
    )
