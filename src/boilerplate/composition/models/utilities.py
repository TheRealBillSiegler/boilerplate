"""Composition utility functions."""

from collections.abc import Iterable

from boilerplate.composition.models.json_types import JSON


def walk_counts(obj: object) -> tuple[int, int]:
    """Walks a JSON-like object and counts (keys, scalars)."""
    if isinstance(obj, dict):
        k = len(obj)
        s = 0
        for v in obj.values():
            k2, s2 = walk_counts(v)
            k += k2
            s += s2
        return k, s
    if isinstance(obj, list):
        k = 0
        s = 0
        for v in obj:
            k2, s2 = walk_counts(v)
            k += k2
            s += s2
        return k, s
    return 0, 1


def max_depth(obj: object, *, _depth: int = 0) -> int:
    """Computes maximum nesting depth for a JSON-like object."""
    if isinstance(obj, dict):
        if not obj:
            return _depth + 1
        return max(max_depth(v, _depth=_depth + 1) for v in obj.values())
    if isinstance(obj, list):
        if not obj:
            return _depth + 1
        return max(max_depth(v, _depth=_depth + 1) for v in obj)
    return _depth


def top_level_user_fields(mapping: dict[str, JSON]) -> int:
    """Counts top-level question fields (non-directive keys)."""
    return sum(1 for k in mapping if not k.startswith("_"))


def directives_present(mapping: dict[str, JSON]) -> list[str]:
    """Returns a sorted list of directive keys present (leading underscore)."""
    return sorted([k for k in mapping if k.startswith("_")])


def aggregate_delta_counts(deltas: Iterable[dict[str, JSON] | None]) -> tuple[int, int]:
    """Aggregates (keys, scalars) across provided delta mappings."""
    total_keys = 0
    total_scalars = 0
    for d in deltas:
        if not d:
            continue
        k, s = walk_counts(d)
        total_keys += k
        total_scalars += s
    return total_keys, total_scalars
