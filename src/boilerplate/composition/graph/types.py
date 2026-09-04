"""Domain types for dependency resolution (composition-owned)."""

# Mapping from a template (by specifier string) to the list of its direct dependencies
type DependencyMap = dict[str, list[str]]

__all__ = [
    "DependencyMap",
]
