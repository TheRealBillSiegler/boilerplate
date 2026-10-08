"""The release a layer update targets."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from boilerplate.composition.updating import LayerRelease


class TestLayerRelease:
    def test_holds_the_layer_its_source_and_the_target_ref(self) -> None:
        release = LayerRelease(layer="core", source=Path("repos/core"), ref="v2")

        assert (release.layer, release.source, release.ref) == (
            "core",
            Path("repos/core"),
            "v2",
        )

    def test_release_is_immutable(self) -> None:
        release = LayerRelease(layer="core", source=Path("repos/core"), ref="v2")

        with pytest.raises(ValidationError):
            release.ref = "v3"  # pyright: ignore[reportAttributeAccessIssue]
