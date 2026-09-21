"""JSON-compatible types and normalization helpers.

Kept in a dedicated module for reuse without importing engine modules. Provides
small, explicit helpers to normalize values into JSON-compatible structures.
Unknown objects raise ``TypeError``.
"""

import os
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePath
from typing import Final, TypeGuard, cast

# Recursive JSON-compatible type alias (Python 3.12+ syntax)
type JSON = None | bool | int | float | str | list["JSON"] | dict[str, "JSON"]

# Concrete helpers to improve readability and typing in guards and overloads.
type JSONObject = dict[str, JSON]
type JSONArray = list[JSON]

# Broader input type accepted by public normalization helpers.
# Allows Mappings/Sequences of JSON-like values, common filesystem and byte
# types. Output is always canonical JSON.
type JSONLike = (
    JSON
    | Mapping[str, "JSONLike"]
    | Sequence["JSONLike"]
    | os.PathLike[str]
    | os.PathLike[bytes]
    | bytes
    | bytearray
)

# Runtime helpers that mirror the root JSON-compatible types above.
# Useful for validation messages and isinstance checks without reflecting on the
# recursive type alias at runtime.
SUPPORTED_JSON_ROOT_TYPES: Final[tuple[type[object], ...]] = (
    type(None),
    bool,
    int,
    float,
    str,
    list,
    dict,
)
SUPPORTED_JSON_TYPE_NAMES: Final[str] = "None, bool, int, float, str, list, dict"


def is_json_object(value: JSON) -> TypeGuard[JSONObject]:
    """Return True if value is a JSON object.

    Args:
        value: A JSON-compatible value.

    Returns:
        True if the value is a ``dict[str, JSON]``, else False.
    """
    return isinstance(value, dict)


def is_json_array(value: JSON) -> TypeGuard[JSONArray]:
    """Return True if value is a JSON array.

    Args:
        value: A JSON-compatible value.

    Returns:
        True if the value is a ``list[JSON]``, else False.
    """
    return isinstance(value, list)


def _coerce_json(value: object) -> JSON:
    """Coerce a value to JSON-compatible types recursively (strict)."""
    if isinstance(value, bytearray):
        # Normalize bytearray via bytes -> str using fsdecode for portability.
        return cast(JSON, os.fsdecode(bytes(value)))
    if isinstance(value, Path | PurePath | os.PathLike | bytes):
        # Use os.fsdecode to obtain a str reliably across platforms and encodings.
        return cast(JSON, os.fsdecode(value))
    if isinstance(value, Mapping):
        out: JSONObject = {}
        for k, v in value.items():
            if not isinstance(k, str):
                raise TypeError(
                    f"JSON object keys must be strings, got {type(k).__name__}: {k!r}"
                )
            out[k] = _coerce_json(v)
        return cast(JSON, out)
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return cast(JSON, [_coerce_json(v) for v in value])
    if isinstance(value, str | int | float | bool) or value is None:
        return cast(JSON, value)
    raise TypeError(f"Value of type {type(value).__name__} is not JSON-serializable")


def ensure_json(value: JSONLike) -> JSON:
    """Normalize a value to JSON-compatible types.

    Args:
        value: A JSONLike value to normalize.

    Returns:
        A JSON-compatible value with deterministic, cross-platform handling for
        paths and byte-like inputs.

    Raises:
        TypeError: If a mapping contains non-string keys or the value is an
            unknown object type.

    Examples:
        >>> ensure_json(Path("x"))
        'x'
        >>> class X: ...
        >>> import pytest
        >>> with pytest.raises(TypeError):
        ...     ensure_json(X())
    """
    return _coerce_json(value)


__all__ = [
    "JSON",
    "JSONArray",
    "JSONLike",
    "JSONObject",
    "ensure_json",
    "is_json_array",
    "is_json_object",
]
