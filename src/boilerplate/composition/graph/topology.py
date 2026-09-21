"""Dependency normalization and topological sequencing per design 04 Stage 2."""

import graphlib

from boilerplate.composition.graph.exceptions import DependencyCycleError
from boilerplate.composition.graph.types import DependencyMap


def normalize_dependencies(deps: DependencyMap) -> DependencyMap:
    """Normalize a dependency map: dedupe, add missing keys, reject self-cycles.

    Args:
        deps: Raw DependencyMap that may contain duplicates, missing keys,
            or self-dependencies.

    Returns:
        Normalized DependencyMap with:
        - Deduplicated dependency lists, preserving declaration order
          (order carries precedence semantics and is never sorted)
        - All referenced nodes present as keys with empty lists if needed
        - No self-dependencies

    Raises:
        DependencyCycleError: If any node depends on itself (self-cycle).

    Examples:
        >>> deps = {"A": ["C", "B", "C"], "B": ["D"]}  # Missing D key; duplicate C
        >>> result = normalize_dependencies(deps)
        >>> {k: result[k] for k in sorted(result)}
        {'A': ['C', 'B'], 'B': ['D'], 'C': [], 'D': []}
    """
    # Check for self-dependencies first
    for node, node_deps in deps.items():
        if node in node_deps:
            raise DependencyCycleError(
                f"Self-dependency detected: '{node}' depends on itself"
            )

    # Create normalized map
    normalized: DependencyMap = {}

    # Deduplicate while preserving declaration order; track all referenced nodes
    all_nodes: set[str] = set(deps.keys())
    for node, node_deps in deps.items():
        deduped_deps = list(dict.fromkeys(node_deps))
        normalized[node] = deduped_deps
        all_nodes.update(deduped_deps)

    # Ensure all referenced nodes exist as keys. Sort so insertion order is
    # deterministic under hash randomization.
    for node in sorted(all_nodes):
        if node not in normalized:
            normalized[node] = []

    return normalized


def toposort_dependencies(deps: DependencyMap) -> list[str]:
    """Return items in dependency-first sequence.

    Independent roots (nodes no other node depends on) are processed in
    lexicographic order. Within each root's reachable subgraph, a post-order
    DFS honors the declaration order of each dependency list, so
    later-declared siblings appear later (and win file/config conflicts). A
    dependency shared by multiple nodes is emitted exactly once, at its first
    occurrence.

    Args:
        deps: DependencyMap where each item maps to the list of its direct
            dependencies in declaration order.

    Returns:
        List of items in dependency-first order, deterministic across runs
        and platforms.

    Raises:
        DependencyCycleError: If the dependencies contain a cycle.

    Examples:
        >>> deps = {"A": ["Z", "B"], "B": [], "Z": []}
        >>> toposort_dependencies(deps)
        ['Z', 'B', 'A']
    """
    # Normalize the dependencies first
    normalized_deps = normalize_dependencies(deps)

    # graphlib is used purely for cycle detection; ordering comes from the
    # DFS below (declaration order, not graphlib's ready-batch order).
    ts: graphlib.TopologicalSorter[str] = graphlib.TopologicalSorter(normalized_deps)
    try:
        ts.prepare()
    except graphlib.CycleError as e:
        raise DependencyCycleError(str(e)) from e

    # Roots are nodes that appear in no dependency list. In a DAG every node
    # is reachable from at least one root, so visiting all roots covers the
    # whole graph.
    referenced: set[str] = set()
    for node_deps in normalized_deps.values():
        referenced.update(node_deps)
    roots = sorted(node for node in normalized_deps if node not in referenced)

    order: list[str] = []
    seen: set[str] = set()

    # Recursive DFS: design 04 caps chain depth at 20, far below the
    # recursion limit; switch to an iterative walk if that cap ever grows.
    def visit(node: str) -> None:
        if node in seen:
            return
        seen.add(node)
        for dep in normalized_deps[node]:
            visit(dep)
        order.append(node)

    for root in roots:
        visit(root)
    return order


__all__ = ["normalize_dependencies", "toposort_dependencies"]
