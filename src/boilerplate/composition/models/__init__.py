"""Core data models used across composition and rendering.

This package defines small, typed models that represent composition
entities such as layers, graphs, and schemas.

- Composition, CompositionLayer: High-level composition structures.
- CompositionGraph, GraphNode: Graph structures for dependencies.

Example:
    >>> from boilerplate.composition.models import Composition, CompositionLayer
    >>> layer = CompositionLayer(name="base", version="1.0.0", path="base", values={})
    >>> Composition(
    ...     graph={"nodes": {}, "edges": {}, "sequence": []},
    ...     sequence=[],
    ...     layers=[layer],
    ...     final={},
    ... )  # doctest: +ELLIPSIS
    Composition(...)
"""

from boilerplate.composition.models.composition import Composition
from boilerplate.composition.models.composition_layer import CompositionLayer
from boilerplate.composition.models.composition_stats import CompositionStats
from boilerplate.composition.models.graph import CompositionGraph, GraphNode
from boilerplate.composition.models.utilities import (
    aggregate_delta_counts,
    directives_present,
    max_depth,
    top_level_user_fields,
    walk_counts,
)

__all__ = [
    "Composition",
    "CompositionGraph",
    "CompositionLayer",
    "CompositionStats",
    "GraphNode",
    "aggregate_delta_counts",
    "directives_present",
    "max_depth",
    "top_level_user_fields",
    "walk_counts",
]
