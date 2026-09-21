"""Deterministic JSON writer utilities (engine-independent)."""

import json
from pathlib import Path

from boilerplate.composition.models.json_types import JSON


def dump_json(data: dict[str, JSON]) -> str:
    """Serialize a mapping to deterministic JSON text.

    - Preserves insertion order
    - Pretty printed (2 spaces)
    - UTF-8, with trailing newline when written
    """
    return json.dumps(data, sort_keys=False, indent=2, ensure_ascii=False) + "\n"


def write_json(data: dict[str, JSON], path: Path) -> None:
    """Write deterministic JSON to ``path`` using UTF-8 and LF newlines."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_json(data), encoding="utf-8", newline="\n")


__all__ = ["dump_json", "write_json"]
