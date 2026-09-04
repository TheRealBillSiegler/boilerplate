"""Composition models for immutable template artifacts (composition-owned)."""

from pydantic import BaseModel, ConfigDict, Field

from boilerplate.composition.models.composition_layer import CompositionLayer
from boilerplate.composition.models.composition_stats import CompositionStats
from boilerplate.composition.models.graph import CompositionGraph, GraphNode
from boilerplate.composition.models.json_types import JSON
from boilerplate.composition.models.utilities import (
    aggregate_delta_counts,
    directives_present,
    max_depth,
    top_level_user_fields,
    walk_counts,
)
from boilerplate.composition.tasks import normalize_tasks


class Composition(BaseModel):
    """Full composition artifact for engine + CLI."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    graph: CompositionGraph
    sequence: list[str]
    layers: list[CompositionLayer]
    final: dict[str, JSON]
    schema_version: str = Field(default="composition/1")

    @property
    def merged_questions_schema(self) -> dict[str, JSON]:
        """Returns merged questions schema with directive keys removed.

        This provides the canonical questionnaire that should be used across
        all layers during rendering, containing all merged question variables
        without Copier directive keys (those starting with '_').

        Returns:
            The merged questions schema for use in Copier workers.
        """
        return {k: v for k, v in self.final.items() if not str(k).startswith("_")}

    @property
    def stats(self) -> "CompositionStats":
        """Domain-centric metrics for this composition.

        Returns a typed object with composition-focused fields.
        """
        total_keys, total_scalars = walk_counts(self.final)
        task_count = len(normalize_tasks(self.final))
        delta_keys, delta_scalars = aggregate_delta_counts(
            layer.delta for layer in self.layers
        )
        return CompositionStats(
            layers_count=len(self.layers),
            total_keys=total_keys,
            total_scalars=total_scalars,
            top_level_fields=top_level_user_fields(self.final),
            directives=directives_present(self.final),
            tasks=task_count,
            max_depth=max_depth(self.final),
            delta_keys=(delta_keys if delta_keys > 0 else None),
            delta_scalars=(delta_scalars if delta_scalars > 0 else None),
        )

    # --- Domain snapshots ---
    def stats_mapping(self) -> dict[str, JSON]:
        """Canonical stats mapping for emission.

        Includes a convenience top-level "layers" alias matching layers_count.
        """
        s = self.stats
        return {"layers": s.layers_count, **s.model_dump()}


__all__ = [
    "JSON",
    "Composition",
    "CompositionGraph",
    "CompositionLayer",
    "CompositionStats",
    "GraphNode",
]
