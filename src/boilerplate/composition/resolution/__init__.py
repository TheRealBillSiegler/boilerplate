"""Resolution of templates into concrete, versioned selections.

This package resolves user-provided identifiers (names/tags) and dependency
constraints to a concrete set of templates and versions to use in planning
and rendering.

- Resolver: Performs resolution using available catalogs.
- Resolution: Result object capturing selected templates and details.

Canonical import:
        >>> from boilerplate.composition.resolution import (
        ...     Resolver,
        ...     Resolution,
        ... )  # doctest: +SKIP

Examples:
        >>> # resolver.resolve(...) returns a Resolution (doctest: +SKIP)
        >>> isinstance(Resolver().resolve(catalog, spec), Resolution)  # doctest: +SKIP
        True
"""

from boilerplate.composition.resolution.models import Resolution
from boilerplate.composition.resolution.resolver import Resolver

__all__ = [
    "Resolution",
    "Resolver",
]
