"""Resolver for template dependency graphs (composition-owned).

Provides an object-oriented API for resolving a template reference into a
dependency map and a corresponding template lookup. This lives alongside the
Resolution model to keep the resolution concern cohesive.
"""
# Spec: docs/design/04-composition-engine.md §Stage 1 — Resolver

from collections.abc import Sequence
from logging import getLogger

from boilerplate.catalog import TemplateCatalog
from boilerplate.common.exceptions import InvalidTemplateSpecifierError
from boilerplate.composition.graph import (
    DependencyMap,
    DependencyNotFoundError,
    VersionConflictError,
)
from boilerplate.composition.resolution import Resolution
from boilerplate.models.template_info import TemplateInfo
from boilerplate.types.template_specifier import TemplateSpecifier

_logger = getLogger(__name__)


class Resolver:
    """Resolves template dependencies from a catalog.

    Methods in this class are pure with respect to inputs and the provided
    registry; no side effects beyond logging. Resolution walks the
    ``meta.extends`` chain, validates references exist in the registry, and
    returns a complete mapping of template specifiers to their direct
    dependency specifiers along with a map of specifier to TemplateInfo.

    Contract:
    - Input ``template_ref`` may be ``name`` or ``name@version``.
    - Registry must implement lookups for both latest and versioned resolution.
    - No cycle detection is performed here (handled by the graph layer).
    - Dependency lists preserve the order specified in ``meta.extends``.
    """

    def resolve(self, template_ref: str, registry: TemplateCatalog) -> Resolution:
        """Resolves a template reference into a complete dependency map and templates.

        Args:
            template_ref: Template identifier (e.g., ``name`` or ``name@version``).
            registry: Catalog used to resolve templates and their dependencies.

        Returns:
            Frozen model containing the dependency map (by specifier
            string) and a templates map from specifier to TemplateInfo.

        Raises:
            DependencyNotFoundError: If any referenced template cannot be found.
            VersionConflictError: If the same template name resolves to two
                different versions in the graph (diamond dependency with
                version disagreement).
        """
        _logger.debug("Resolving dependencies for: %s", template_ref)

        # Fetch the root template
        root_template = self._fetch_template(template_ref, registry)

        # Build the dependency map
        dependency_map: DependencyMap = {}
        templates_map: dict[str, TemplateInfo] = {}
        visited: set[str] = set()
        # Name -> (specifier string, requiring specifier or None for the root)
        # for the first version of that name seen, to detect diamond conflicts.
        first_seen_by_name: dict[str, tuple[str, str | None]] = {}

        def _add_template(template: TemplateInfo, required_by: str | None) -> None:
            """Recursively adds template and its dependencies to the map.

            Ensures each template is processed at most once; preserves the order of
            dependencies as declared on the template's ``meta.extends``.

            Raises:
                VersionConflictError: If ``template``'s name was already resolved
                    to a different version elsewhere in the graph.
            """
            specifier_str = str(template.specifier)

            # Avoid infinite recursion
            if specifier_str in visited:
                return
            visited.add(specifier_str)

            existing = first_seen_by_name.get(template.name)
            if existing is None:
                first_seen_by_name[template.name] = (specifier_str, required_by)
            elif existing[0] != specifier_str:
                raise VersionConflictError(
                    self._conflict_message(
                        template.name, existing, (specifier_str, required_by)
                    )
                )

            _logger.debug("Adding template to dependency map: %s", specifier_str)

            # Track the template for the specifier
            templates_map[specifier_str] = template

            # Initialize dependencies list for this template
            dependencies: list[str] = []

            # Process each dependency
            for ref in self._iter_extends(template.meta.extends):
                dependency = self._fetch_template(ref, registry)
                dep_specifier_str = str(dependency.specifier)
                dependencies.append(dep_specifier_str)

                # Recursively add the dependency
                _add_template(dependency, required_by=specifier_str)

            # Add this template's dependencies to the map
            dependency_map[specifier_str] = dependencies

        # Start the recursive traversal
        _add_template(root_template, required_by=None)

        _logger.debug(
            "Resolved %d templates in dependency map: %s",
            len(dependency_map),
            list(dependency_map.keys()),
        )

        return Resolution(deps=dependency_map, templates=templates_map)

    @staticmethod
    def _conflict_message(
        name: str,
        first: tuple[str, str | None],
        second: tuple[str, str | None],
    ) -> str:
        """Builds a diamond version-conflict message naming both requiring paths.

        Args:
            name: Template name shared by both conflicting specifiers.
            first: Specifier string and requiring specifier (``None`` for the
                root), for the version encountered first.
            second: Same shape as ``first``, for the conflicting version.

        Returns:
            Message per docs/design/04-composition-engine.md
            §Version conflict resolution.
        """

        def _describe(entry: tuple[str, str | None]) -> str:
            specifier_str, required_by = entry
            version = specifier_str.split("@", 1)[1]
            by = f"by '{required_by}'" if required_by is not None else "as the root"
            return f"{version} ({by})"

        return (
            f"Template '{name}' required at version {_describe(first)} "
            f"and {_describe(second)}"
        )

    @staticmethod
    def _iter_extends(extends: Sequence[str] | None) -> Sequence[str]:
        """Normalizes and iterates over ``extends`` safely.

        Args:
            extends: Sequence of dependency references or None.

        Returns:
            Empty sequence if None, else the original sequence.
        """
        return extends or []

    @staticmethod
    def _fetch_template(reference: str, registry: TemplateCatalog) -> TemplateInfo:
        """Loads a template by reference.

        Reference can be ``"name@version"`` for a specific version or
        ``"name"`` for latest.

        Resolution rules:
        - Unversioned reference (no ``@``): resolve the latest available
          version.
        - Versioned reference (``name@version``): parse and resolve that
          exact version; if parsing fails, raise an error rather than
          changing behavior.

        Args:
            reference: Template reference string.
            registry: TemplateCatalog providing resolution.

        Returns:
            Resolved template.

        Raises:
            DependencyNotFoundError: If the template cannot be resolved.
        """
        _logger.debug("Loading template: %s", reference)

        # If no '@' is present, treat as unversioned and resolve to latest
        if "@" not in reference:
            template = registry.resolve_latest(reference)
        else:
            # Versioned reference: must parse successfully; otherwise, surface
            # a clear not-found error without silently changing semantics.
            try:
                specifier = TemplateSpecifier.from_string(reference)
            except InvalidTemplateSpecifierError as exc:
                raise DependencyNotFoundError(
                    f"Invalid template specifier: {reference}"
                ) from exc
            template = registry.resolve(specifier.name, specifier.version)

        if template is None:
            raise DependencyNotFoundError(f"Template not found: {reference}")

        return template


__all__ = ["Resolver"]
