"""Merge strategies for combining configuration values (composition)."""

from packaging.version import Version

from boilerplate.composition.merging.exceptions import MergeConflictError


def override(values: list[object], _: str) -> object:
    """Returns the last value (later layers override earlier ones)."""
    return values[-1]


def accumulate(values: list[object], _: str) -> list[object]:
    """Concatenates lists or appends scalars in order (for _tasks, secrets)."""
    result: list[object] = []
    for value in values:
        if isinstance(value, list):
            result.extend(value)
        else:
            result.append(value)
    return result


def union(values: list[object], _: str) -> list[object]:
    """Returns a de-duplicated union preserving first-seen order."""
    seen = set()
    result = []
    for value in values:
        if isinstance(value, list):
            for item in value:
                if item not in seen:
                    seen.add(item)
                    result.append(item)
        elif value not in seen:
            seen.add(value)
            result.append(value)
    return result


def merge_questions(values: list[object], key: str) -> object:
    """Merges question values: dicts overlay, lists dedupe-concat, scalars override."""
    if not values:
        raise MergeConflictError(f"No values provided for '{key}'")

    merged = values[0]
    for idx, value in enumerate(values):
        if idx == 0:
            continue
        if isinstance(merged, dict) and isinstance(value, dict):
            merged = {**merged, **value}
        elif isinstance(merged, list) and isinstance(value, list):
            merged = list(dict.fromkeys(merged + value))
        elif isinstance(value, type(merged)):
            merged = value
        else:
            raise MergeConflictError(
                f"Incompatible types for '{key}': {type(merged).__name__} vs {type(value).__name__}",
            )
    return merged


def intersect_versions(values: list[object], key: str) -> str:
    """Returns the highest PEP 440 version string among the inputs."""
    versions = []
    for v in values:
        if not isinstance(v, str):
            raise MergeConflictError(f"Non-string value for version in '{key}': {v!r}")
        versions.append(Version(v))
    if not versions:
        raise MergeConflictError(f"No versions provided for '{key}'")
    return str(max(versions))
