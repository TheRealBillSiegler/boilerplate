"""Merges Copier configuration dictionaries for composition.

Provides explicit strategies to combine configuration values across extended
template hierarchies. This module focuses strictly on merging and does not
perform domain-specific normalization.
"""
# Spec: docs/design/04-composition-engine.md §Configuration Merger

from collections.abc import Callable
from typing import ClassVar

from boilerplate.composition.merging.strategies import (
    accumulate,
    intersect_versions,
    merge_questions,
    override,
    union,
)
from boilerplate.composition.tasks import TASKS_KEY
from boilerplate.integrations.copier_types import Template, template_public_attr_names

# Type alias for merge functions: (values, key) -> merged_result
MergeFunction = Callable[[list[object], str], object]


class CopierConfigMerger:
    """Merges question variables from multiple Copier configurations.

    Only user-defined questions (non-underscore keys) and minimal coordination
    fields are combined across layers.
    """

    mergeable_keys: ClassVar[set[str]] = {
        "_min_copier_version",
        TASKS_KEY,
        "_secret_questions",
        "_jinja_extensions",
    }

    @classmethod
    def get_layer_local_keys(cls) -> set[str]:
        """Return Copier fields that are layer-local and not merged."""
        copier_fields = {
            f"_{attr}"
            for attr in template_public_attr_names(Template)
            if attr != "questions_data"
        }
        return copier_fields - cls.mergeable_keys

    def __init__(self) -> None:
        """Initialize merger with strategy mapping for mergeable keys."""
        self.merge_strategies: dict[str, MergeFunction] = {
            "_min_copier_version": intersect_versions,
            TASKS_KEY: accumulate,
            "_secret_questions": accumulate,
            "_jinja_extensions": union,
        }

    def merge(self, configurations: list[dict[str, object]]) -> dict[str, object]:
        """Merge multiple configuration dictionaries into unified questions."""
        merged: dict[str, object] = {}
        layer_local_keys = self.get_layer_local_keys()

        # Collect all unique keys while preserving order
        all_keys = []
        seen = set()
        for config in configurations:
            for key in config:
                if key not in seen:
                    seen.add(key)
                    all_keys.append(key)

        for key in all_keys:
            values = [config[key] for config in configurations if key in config]

            # Skip layer-local keys
            if key in layer_local_keys:
                continue

            # Apply merge strategy based on key type
            if key in self.mergeable_keys:
                merge_fn = self.merge_strategies.get(key, override)
                merged[key] = merge_fn(values, key)
            elif not key.startswith("_"):  # Regular questions
                merged[key] = merge_questions(values, key)
            # Skip other underscore keys

        return merged
