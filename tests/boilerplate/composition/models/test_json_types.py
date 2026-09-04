from pathlib import Path
from typing import cast

import pytest

from boilerplate.composition.models.json_types import (
    JSONLike,
    ensure_json,
    is_json_array,
    is_json_object,
)


def test_ensure_json_coerces_path_and_nested() -> None:
    data = {"p": Path("/x"), "lst": [1, Path("/y")], "nested": {"k": Path("/z")}}
    out = ensure_json(data)
    assert is_json_object(out)
    # On Windows, Path("/x") stringifies to "\\x"; accept either separator
    assert str(out["p"]).replace("\\", "/") == "/x"
    lst = out["lst"]
    assert is_json_array(lst)
    assert str(lst[1]).replace("\\", "/") == "/y"
    nested = out["nested"]
    assert is_json_object(nested)
    assert str(nested["k"]).replace("\\", "/") == "/z"


def test_ensure_json_rejects_non_string_keys() -> None:
    with pytest.raises(TypeError):
        ensure_json({1: "x"})  # type: ignore[dict-item]


def test_ensure_json_rejects_unknown_object() -> None:
    class X: ...

    with pytest.raises(TypeError):
        ensure_json(cast(JSONLike, X()))


def test_unknown_behavior_is_strict() -> None:
    class X: ...

    with pytest.raises(TypeError):
        ensure_json(cast(JSONLike, X()))


def test_typeguards() -> None:
    obj = ensure_json({"a": [1, 2]})
    assert is_json_object(obj)
    assert is_json_array(obj["a"])
