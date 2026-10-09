"""Plan an add: every check that comes before staging."""
# Spec: docs/design/06-project-lifecycle.md §Part 2: Project Update

from pathlib import Path

from pydantic import ValidationError

from boilerplate.common.exceptions import MetadataValidationError
from boilerplate.composition.adding.add_plan import AddPlan
from boilerplate.composition.adding.add_request import AddRequest
from boilerplate.composition.adding.ancestor_check import check_ancestors
from boilerplate.composition.adding.layer_tasks import own_tasks
from boilerplate.composition.updating.layer_release import LayerRelease
from boilerplate.composition.updating.release_views import ReleaseViews
from boilerplate.composition.updating.walk.layer_sources import read_layer_sources
from boilerplate.composition.updating.walk.lock_releases import lock_releases
from boilerplate.composition.updating.walk.target_releases import named_releases
from boilerplate.models import BoilerplateLock
from boilerplate.models.template_meta import TemplateMeta
from boilerplate.repository.release_checkouts import ReleaseCheckouts

__all__ = ["plan_add"]


def plan_add(
    project: Path,
    request: AddRequest,
    lock: BoilerplateLock,
    checkouts: ReleaseCheckouts,
    workdir: Path,
) -> AddPlan:
    """Decide what adding `request`'s layer does, without changing anything.

    Resolves the layer's release, checks its ancestors against the lock and
    builds the layer's view: the questions of the layer and its ancestors, each
    defined by the merged schema of the project's layers plus the new one.

    Args:
        project: The project, a git repository root.
        request: What the user asked of the add.
        lock: The project's lock.
        checkouts: The release checkouts the view reads; they must outlive the
            plan, since the view holds paths into them.
        workdir: A directory to assemble the templates directories in; it must
            outlive the plan too.

    Returns:
        The plan.

    Raises:
        MetadataValidationError: If the template has no valid ``boilerplate.yml``
            or names a layer other than the one requested.
        TemplateNotFoundError: If the release reads as no version.
        AddAncestorsMissingError: If an ancestor is not in the lock.
        AddAncestorVersionError: If an ancestor's recorded version fails the
            layer's ``extends`` reference.
        plumbum.commands.processes.ProcessExecutionError: If the source cannot
            check the release out.
    """
    sources = read_layer_sources(project, lock)
    at_lock = lock_releases(lock, sources)
    releases, versions = named_releases(
        {request.name: request.source}, {request.name: request.ref}, checkouts
    )
    release = releases[request.name]
    template = checkouts.get(release.source, release.ref).path
    meta = _load_meta(template, request.name)
    check_ancestors(
        request.name,
        meta.extends,
        {entry.name: entry.version for entry in lock.layers},
        lambda layer: (
            _load_meta(
                checkouts.get(at_lock[layer].source, at_lock[layer].ref).path, layer
            ).extends
        ),
    )
    views = ReleaseViews(checkouts, workdir=workdir)
    after = {**at_lock, request.name: release}
    view = views.step_view(request.name, after)
    return AddPlan(
        lock=lock,
        release=LayerRelease(
            layer=request.name, source=release.source, ref=release.ref
        ),
        version=str(versions[request.name]),
        view=view,
        tasks=tuple(own_tasks(template)),
        needs_unsafe=views.needs_unsafe(request.name, after),
    )


def _load_meta(template: Path, name: str) -> TemplateMeta:
    """Read the ``boilerplate.yml`` of the checkout of layer `name`.

    Raises:
        MetadataValidationError: If the file is missing or invalid, or names a
            different layer.
    """
    try:
        meta = TemplateMeta.load(template)
    except (FileNotFoundError, ValidationError) as error:
        raise MetadataValidationError(
            f"Layer '{name}': boilerplate.yml is missing or invalid: {error}"
        ) from error
    if meta.name != name:
        raise MetadataValidationError(
            f"Layer '{name}': the template at {template} is named '{meta.name}'."
        )
    return meta
