"""YAML/JSON-safe serialization helpers independent of engine.*.

Provides:
- serialize_for_yaml: deeply normalize values to JSON-compatible types
- extract_complete_copier_config: build a full copier.yml-style config
"""

from typing import Any, cast

from packaging.version import Version

from boilerplate.composition.models.json_types import JSONLike, ensure_json
from boilerplate.composition.tasks import TASKS_KEY, coerce_task
from boilerplate.integrations.copier_types import Template as CopierTemplate
from boilerplate.integrations.copier_types import template_public_attr_names


def serialize_for_yaml(data: dict[str, Any]) -> dict[str, object]:
    """Deeply normalizes values into a YAML/JSON-safe structure.

    DRY with JSON normalization: delegates general value coercion to
    ``ensure_json`` for deterministic, cross-platform handling while preserving
    two YAML-specific behaviors:
    - Stringify mapping keys (JSON/YAML-safe keys are strings)
    - Special-case Copier Task objects under ``_tasks``: convert each task with
      a ``cmd`` attribute into a list form of that command.
    """

    def _preprocess(value: object, *, parent_key: str | None = None) -> object:
        # Special handling for copier tasks only when under the _tasks field
        if parent_key == TASKS_KEY and isinstance(value, list | tuple | set):
            out: list[object] = []
            for item in value:
                if hasattr(item, "cmd"):
                    # Represent command sequences as lists for YAML/JSON safety
                    out.append(coerce_task(item))
                else:
                    out.append(_preprocess(item, parent_key=parent_key))
            return out
        # Containers: stringify keys, recurse for values to catch nested _tasks
        if isinstance(value, dict):
            return {str(k): _preprocess(v, parent_key=str(k)) for k, v in value.items()}
        if isinstance(value, list | tuple | set):
            return [_preprocess(v, parent_key=parent_key) for v in value]
        # Primitives and everything else: leave as-is for ensure_json to handle
        return value

    # First pass: enforce key stringification and _tasks semantics
    prepped: dict[str, object] = {
        str(k): _preprocess(v, parent_key=str(k)) for k, v in data.items()
    }

    # Second pass: normalize using the canonical JSON coercer
    normalized = ensure_json(cast(JSONLike, prepped))
    # ensure_json returns JSON; guarantee mapping shape for caller expectations
    assert isinstance(normalized, dict)
    return cast(dict[str, object], normalized)


def extract_complete_copier_config(copier_template: CopierTemplate) -> dict[str, Any]:
    """Extracts complete Copier configuration using full API interface.

    Converts all public Template attributes to copier.yml-style fields, with
    questions_data expanded as top-level keys.

    Reading those attributes forces ``local_abspath``, which clones a
    git-backed template into a temporary directory. Templates reaching this
    function come from the catalog rather than from a Copier ``Worker``, so
    nothing else owns that clone and nothing else would remove it; this
    function releases it once every attribute has been read. Copier's
    ``Template._cleanup`` is a no-op when no clone was made and when one was
    already removed, so calling it unconditionally is safe.

    Args:
        copier_template: Template whose configuration to read. Its temporary
            clone, if it made one, no longer exists when this returns.

    Returns:
        A ``copier.yml``-style mapping: Copier's own fields under their
        ``_``-prefixed names, questions expanded as top-level keys.
    """
    config: dict[str, Any] = {}

    # Extract ALL public attributes from Copier Template (names come from the
    # class so the set matches what the merger treats as layer-local)
    try:
        template_attrs = {
            attr: getattr(copier_template, attr)
            for attr in template_public_attr_names(type(copier_template))
        }
    finally:
        copier_template._cleanup()  # pyright: ignore[reportPrivateUsage]

    for attr, value in template_attrs.items():
        if attr == "questions_data":
            config.update(value)
            continue

        copier_field = f"_{attr}"
        if isinstance(value, tuple | set):
            config[copier_field] = list(value)
        elif isinstance(value, Version):
            # Template.min_copier_version returns a packaging.version.Version;
            # stringify at this boundary so downstream YAML/JSON serialization
            # and the merger's intersect_versions strategy (which expects str)
            # both work.
            config[copier_field] = str(value)
        elif value is not None:  # Skip None to use Copier defaults
            config[copier_field] = value

    return config


__all__ = ["extract_complete_copier_config", "serialize_for_yaml"]
