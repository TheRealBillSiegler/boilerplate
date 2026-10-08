"""An ordered resolution applies its layers in the order it is given."""

import pytest
from pydantic import ValidationError

from boilerplate.composition.resolution.models.ordered_resolution import (
    OrderedResolution,
)

# Two layers that extend the same ancestor and neither the other, the shape a
# project has after it adds a second layer to the first: toposort visits such
# roots in name order, so "docs" would come before "service".
SIBLINGS = {
    "core@1.0.0": [],
    "service@1.0.0": ["core@1.0.0"],
    "docs@1.0.0": ["core@1.0.0"],
}


class TestExecutionSequence:
    def test_follows_the_given_layer_order(self) -> None:
        """Keep the order the project's lock lists, not the name order."""
        resolution = OrderedResolution(
            deps=SIBLINGS, templates={}, layer_order=("core", "service", "docs")
        )

        assert resolution.execution_sequence == [
            "core@1.0.0",
            "service@1.0.0",
            "docs@1.0.0",
        ]


class TestLayerOrder:
    def test_is_required(self) -> None:
        """Refuse a resolution that leaves the execution order out."""
        with pytest.raises(ValidationError):
            OrderedResolution(deps=SIBLINGS, templates={})  # type: ignore[call-arg]
