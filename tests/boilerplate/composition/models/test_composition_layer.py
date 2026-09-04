"""Tests for the CompositionLayer model."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from boilerplate.composition.models import CompositionLayer


def test_composition_layer_immutable(tmp_path: Path) -> None:
    layer = CompositionLayer(
        name="test", version="1.0", path=tmp_path, values={"key": "value"}
    )
    with pytest.raises(ValidationError):
        layer.name = "changed"
