"""Tests for the Composition model."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from boilerplate.composition.models import (
    Composition,
    CompositionGraph,
    CompositionLayer,
    GraphNode,
)


def test_composition_creation(tmp_path: Path) -> None:
    node = GraphNode(name="test", version="1.0", path=tmp_path)
    graph = CompositionGraph(
        nodes={"test@1.0": node}, edges={"test@1.0": []}, sequence=["test@1.0"]
    )
    layer = CompositionLayer(
        name="test", version="1.0", path=tmp_path, values={"key": "value"}
    )

    composition = Composition(
        graph=graph, sequence=["test@1.0"], layers=[layer], final={}
    )

    assert composition.schema_version == "composition/1"
    assert composition.final == {}

    with pytest.raises(ValidationError):
        composition.final = {"changed": "value"}
