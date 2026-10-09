"""Tests for the LockLayer model in lock_layer.py."""

import pytest
from pydantic import ValidationError

from boilerplate.models import JoinedVia, LockLayer
from boilerplate.types import SerializableVersion

CHECKSUM = "sha256:" + "a" * 64


def _fields(**overrides: object) -> dict[str, object]:
    return {
        "name": "core",
        "version": "1.0.0",
        "source": "https://example.com/core.git",
        "checksum": CHECKSUM,
        **overrides,
    }


class TestLockLayerHappyPath:
    """A layer records what the walk needs to know about its last render."""

    def test_parses_the_required_fields(self) -> None:
        layer = LockLayer.model_validate(_fields(commit="abc123"))

        assert layer.name == "core"
        assert layer.version == SerializableVersion("1.0.0")
        assert layer.commit == "abc123"
        assert layer.checksum == CHECKSUM

    def test_the_optional_fields_default_to_none(self) -> None:
        layer = LockLayer.model_validate(_fields())

        assert layer.commit is None
        assert layer.subdirectory is None
        assert layer.source_bundle is None
        assert layer.trust_tier is None
        assert layer.bundle_uri is None
        assert layer.bundle_checksum is None

    def test_ignores_fields_a_later_minor_schema_adds(self) -> None:
        layer = LockLayer.model_validate(_fields(added_later="x"))

        assert not hasattr(layer, "added_later")

    def test_serializes_the_version_as_a_string(self) -> None:
        dumped = LockLayer.model_validate(_fields(version="1.1.0")).model_dump(
            mode="json"
        )

        assert dumped["version"] == "1.1.0"


class TestLockLayerJoinedVia:
    """A layer records how it joined the project: through extends or through add."""

    def test_a_layer_without_the_field_joined_through_extends(self) -> None:
        """Read a lock written before the field existed as an extends layer."""
        layer = LockLayer.model_validate(_fields())

        assert layer.joined_via is JoinedVia.EXTENDS

    def test_reads_the_add_origin(self) -> None:
        layer = LockLayer.model_validate(_fields(joined_via="add"))

        assert layer.joined_via is JoinedVia.ADD

    @pytest.mark.parametrize("origin", ["extends", "add"])
    def test_serializes_the_origin_as_its_name(self, origin: str) -> None:
        dumped = LockLayer.model_validate(_fields(joined_via=origin)).model_dump(
            mode="json"
        )

        assert dumped["joined_via"] == origin

    def test_serializes_the_default_origin(self) -> None:
        """Write the field on every entry, so a reader never has to default it."""
        dumped = LockLayer.model_validate(_fields()).model_dump(mode="json")

        assert dumped["joined_via"] == "extends"

    def test_rejects_an_origin_the_schema_does_not_name(self) -> None:
        with pytest.raises(ValidationError):
            LockLayer.model_validate(_fields(joined_via="adopt"))


class TestLockLayerSadPath:
    """A layer that cannot be trusted is refused."""

    @pytest.mark.parametrize("field", ["name", "version", "source", "checksum"])
    def test_requires(self, field: str) -> None:
        fields = _fields()
        del fields[field]

        with pytest.raises(ValidationError):
            LockLayer.model_validate(fields)

    def test_rejects_an_empty_name(self) -> None:
        with pytest.raises(ValidationError):
            LockLayer.model_validate(_fields(name=""))

    def test_rejects_a_version_that_is_not_pep_440(self) -> None:
        with pytest.raises(ValidationError):
            LockLayer.model_validate(_fields(version="not-a-version"))

    def test_rejects_a_checksum_without_the_algorithm_prefix(self) -> None:
        with pytest.raises(ValidationError):
            LockLayer.model_validate(_fields(checksum="a" * 64))

    def test_is_immutable(self) -> None:
        layer = LockLayer.model_validate(_fields())

        with pytest.raises(ValidationError):
            layer.name = "other"
