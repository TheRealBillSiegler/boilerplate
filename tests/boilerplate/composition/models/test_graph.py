"""Tests for the composition graph models."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from boilerplate.composition.models import CompositionGraph, GraphNode


@pytest.mark.parametrize("field,value", [("name", "changed"), ("version", "2.0")])
def test_graph_node_immutable(tmp_path: Path, field: str, value: str) -> None:
    node = GraphNode(name="test", version="1.0", path=tmp_path)
    with pytest.raises((TypeError, ValidationError)):
        setattr(node, field, value)


def test_composition_graph_creation(tmp_path: Path) -> None:
    node = GraphNode(name="test", version="1.0", path=tmp_path)
    graph = CompositionGraph(
        nodes={"test@1.0": node}, edges={"test@1.0": []}, sequence=["test@1.0"]
    )

    with pytest.raises((TypeError, ValidationError)):
        graph.sequence = ["changed"]
