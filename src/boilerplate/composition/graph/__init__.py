"""Graph utilities for working with template dependency graphs.

This package provides small, focused primitives to build and validate the
directed acyclic graphs (DAGs) used by the composer when resolving template
dependencies.

- DependencyMap: A mapping of node -> list of dependency nodes.
- normalize_dependencies(...): Accepts flexible specs and returns a
    canonical DependencyMap (no duplicates; stable ordering).
- toposort_dependencies(...): Returns a topological sequence where each dependency
    appears before any node that depends on it.

Exceptions:
- DependencyError: Base class for graph-related errors.
- DependencyNotFoundError: A dependency edge references a missing node.
- DependencyCycleError: The graph contains a cycle (not a DAG).
- VersionConflictError: The same template name resolves to different versions.

Canonical import:
    >>> from boilerplate.composition.graph import (
    ...     toposort_dependencies,
    ... )  # doctest: +SKIP

Examples:
        >>> deps = {"app": ["core"], "core": []}
    >>> order = toposort_dependencies(deps)
        >>> order.index("core") < order.index("app")
        True
"""

from boilerplate.composition.graph.exceptions import (
    DependencyCycleError,
    DependencyError,
    DependencyNotFoundError,
    VersionConflictError,
)
from boilerplate.composition.graph.topology import (
    normalize_dependencies,
    toposort_dependencies,
)
from boilerplate.composition.graph.types import DependencyMap

__all__ = [
    "DependencyCycleError",
    "DependencyError",
    "DependencyMap",
    "DependencyNotFoundError",
    "VersionConflictError",
    "normalize_dependencies",
    "toposort_dependencies",
]
