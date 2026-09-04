"""Graph models for composition dependency analysis (composition-owned)."""

from pathlib import Path
from typing import cast

from pydantic import BaseModel, ConfigDict

from boilerplate.composition.models.json_types import JSON


class GraphNode(BaseModel):
    """A node in the composition dependency graph."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    version: str
    path: Path


class CompositionGraph(BaseModel):
    """Dependency graph with deterministic sequencing for composition."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    nodes: dict[str, GraphNode]  # key: canonical specifier e.g. "name@version"
    edges: dict[str, list[str]]  # adjacency; children in declaration order, deduped
    sequence: list[str]  # deterministic render sequence (toposort), cached

    # --- Domain snapshots ---
    def sequence_payload(self) -> dict[str, JSON]:
        """Canonical mapping describing the sequence and layer metadata."""
        layers: list[dict[str, JSON]] = []
        for spec in self.sequence:
            node = self.nodes.get(spec)
            if node is None:
                continue
            layers.append(
                {
                    "specifier": spec,
                    "name": node.name,
                    "version": node.version,
                    "path": str(node.path),
                    # cast dependencies into JSON-compatible list
                    "deps": list(self.edges.get(spec, [])),
                }
            )
        return {
            "sequence": list(self.sequence),
            "layers": cast(JSON, layers),
        }


__all__ = ["CompositionGraph", "GraphNode"]
