"""Unit tests for the Resolution model integrity and immutability."""

import pytest
from pydantic import ValidationError

from boilerplate.composition.resolution import Resolution


def test_resolution_is_immutable_and_types() -> None:
    res = Resolution(deps={"a@1": []}, templates={})

    # Frozen model should not allow attribute reassignment
    with pytest.raises(ValidationError):
        res.deps = {}

    # Types are preserved as provided
    assert isinstance(res.deps, dict)
    assert isinstance(res.templates, dict)
