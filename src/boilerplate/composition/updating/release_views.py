"""Build the views of an update from checkouts of the releases it reads."""

from collections.abc import Mapping, Sequence
from pathlib import Path

from boilerplate.catalog.catalog import TemplateCatalog
from boilerplate.composition.composer import Composer
from boilerplate.composition.graph import DependencyMap
from boilerplate.composition.models.composition import Composition
from boilerplate.composition.models.json_types import JSON
from boilerplate.composition.resolution import Resolver
from boilerplate.composition.resolution.models import OrderedResolution
from boilerplate.composition.tasks import normalize_tasks
from boilerplate.composition.updating.release_ref import ReleaseRef
from boilerplate.composition.updating.update_views import UpdateViews
from boilerplate.composition.views import LayerView, build_step_view
from boilerplate.models.template_info import TemplateInfo
from boilerplate.repository.directory_repository import DirectoryTemplateRepository
from boilerplate.repository.release_checkouts import ReleaseCheckouts
from boilerplate.repository.templates_dir import assemble_templates_dir


class ReleaseViews:
    """Views, ancestors and tasks of a composition at chosen releases.

    A composition is resolved and composed from a templates directory, so each
    set of releases is checked out, copied into a directory of its own and read
    through the existing catalog, ``Resolver`` and ``Composer``. A directory is
    built once per set of releases and kept until ``workdir`` is removed: the
    views hold paths into it for the ancestors' extension files.

    The full composition spans every layer of the releases, in the order the
    releases list them. A project that added layers one after another has no
    single layer whose ancestors cover the rest, so no one layer can be its root.
    """

    def __init__(self, checkouts: ReleaseCheckouts, *, workdir: Path) -> None:
        """Prepare views of the compositions of releases read from `checkouts`.

        Args:
            checkouts: The release checkouts to read; they must outlive the
                views.
            workdir: The directory to assemble templates directories in; the
                caller removes it when the views are no longer used.
        """
        self._checkouts = checkouts
        self._workdir = workdir
        self._catalogs: dict[frozenset[tuple[str, ReleaseRef]], TemplateCatalog] = {}

    def step_view(self, layer: str, releases: Mapping[str, ReleaseRef]) -> LayerView:
        """Return the view an update step of `layer` renders under at `releases`.

        The questions of the layer and its ancestors, each defined by the full
        composition's merged schema at the same releases.

        Args:
            layer: The layer being updated.
            releases: The release of every layer of the project, in the order
                the project applies them.

        Returns:
            The step's view.
        """
        return build_step_view(
            self._compose(layer, releases), self._compose_project(releases)
        )

    def update_views(
        self,
        layer: str,
        *,
        old: Mapping[str, ReleaseRef],
        target: Mapping[str, ReleaseRef],
    ) -> UpdateViews:
        """Return the views an update step of `layer` renders its copies under.

        Args:
            layer: The layer being updated.
            old: The release of every layer at the versions the old copy
                renders.
            target: The release of every layer at the targets.

        Returns:
            The old view and the target view.
        """
        return UpdateViews(self.step_view(layer, old), self.step_view(layer, target))

    def ancestors(
        self, releases: Mapping[str, ReleaseRef]
    ) -> dict[str, tuple[str, ...]]:
        """Return every layer's ancestors, transitively, at `releases`.

        Args:
            releases: The release of every layer of the project.

        Returns:
            The ancestors of each layer in topological order, keyed by layer.
        """
        return {
            layer: tuple(
                name for name in self._sequence(layer, releases) if name != layer
            )
            for layer in releases
        }

    def tasks(self, releases: Mapping[str, ReleaseRef]) -> list[JSON]:
        """Return the accumulated task list of the composition at `releases`.

        Args:
            releases: The release of every layer of the project, in the order
                the project applies them.

        Returns:
            The tasks of every layer in the order `releases` lists them, in
            Copier's shapes.
        """
        return normalize_tasks(self._compose_project(releases).final)

    def _sequence(
        self, layer: str, releases: Mapping[str, ReleaseRef]
    ) -> Sequence[str]:
        """Return `layer` and its ancestors by name, ancestors first."""
        resolution = Resolver().resolve(layer, self._catalog(releases))
        return [
            specifier.split("@", 1)[0] for specifier in resolution.execution_sequence
        ]

    def _compose(self, layer: str, releases: Mapping[str, ReleaseRef]) -> Composition:
        """Resolve and compose `layer` and its ancestors at `releases`."""
        resolution = Resolver().resolve(layer, self._catalog(releases))
        return Composer().compose(resolution)

    def _compose_project(self, releases: Mapping[str, ReleaseRef]) -> Composition:
        """Resolve and compose every layer of `releases`, in the order it lists them."""
        catalog = self._catalog(releases)
        deps: DependencyMap = {}
        templates: dict[str, TemplateInfo] = {}
        for layer in releases:
            resolution = Resolver().resolve(layer, catalog)
            deps.update(resolution.deps)
            templates.update(resolution.templates)
        return Composer().compose(
            OrderedResolution(
                deps=deps, templates=templates, layer_order=tuple(releases)
            )
        )

    def _catalog(self, releases: Mapping[str, ReleaseRef]) -> TemplateCatalog:
        """Return the catalog of the templates directory holding `releases`."""
        key = frozenset(releases.items())
        if key not in self._catalogs:
            templates = assemble_templates_dir(
                {
                    layer: self._checkouts.get(release.source, release.ref).path
                    for layer, release in releases.items()
                },
                self._workdir / f"releases-{len(self._catalogs)}",
            )
            catalog = TemplateCatalog()
            catalog.register_many(
                DirectoryTemplateRepository(templates).load_templates()
            )
            self._catalogs[key] = catalog
        return self._catalogs[key]
