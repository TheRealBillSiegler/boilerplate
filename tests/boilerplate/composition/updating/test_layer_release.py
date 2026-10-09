"""The release a layer update targets."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from boilerplate.composition.updating import LayerRelease
from boilerplate.composition.updating.release_ref import ReleaseRef


class TestLayerRelease:
    def test_holds_the_layer_its_source_and_the_target_ref(self) -> None:
        release = LayerRelease(layer="core", source="repos/core", ref="v2")

        assert (release.layer, release.source, release.ref) == (
            "core",
            "repos/core",
            "v2",
        )

    def test_release_is_immutable(self) -> None:
        release = LayerRelease(layer="core", source="repos/core", ref="v2")

        with pytest.raises(ValidationError):
            release.ref = "v3"  # pyright: ignore[reportAttributeAccessIssue]

    def test_a_url_source_is_kept_as_written(self) -> None:
        """Keep a git URL as a string: as a path it would lose its slashes."""
        url = "https://example.com/org/core.git"

        release = LayerRelease(layer="core", source=url, ref="v2")

        assert release.source == url

    def test_a_path_source_is_refused(self) -> None:
        """Take the source as the answers file records it, never as a path."""
        with pytest.raises(ValidationError):
            LayerRelease.model_validate(
                {"layer": "core", "source": Path("repos/core"), "ref": "v2"}
            )


class TestFromRelease:
    def test_carries_the_source_and_ref_of_the_release_for_the_layer(self) -> None:
        url = "https://example.com/org/core.git"

        release = LayerRelease.from_release("core", ReleaseRef(source=url, ref="v2"))

        assert release == LayerRelease(layer="core", source=url, ref="v2")
