"""Tests for the BoilerplateLock model in boilerplate_lock.py."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from boilerplate.models import LOCK_SCHEMA_VERSION, BoilerplateLock

CHECKSUM = "sha256:" + "a" * 64
HASH = "b" * 64
STAMP = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)


def _layer(name: str, version: str = "1.0.0") -> dict[str, str]:
    return {
        "name": name,
        "version": version,
        "source": f"https://example.com/{name}.git",
        "commit": "abc123",
        "checksum": CHECKSUM,
    }


def _fields(**overrides: object) -> dict[str, object]:
    return {
        "boilerplate_version": "0.3.0",
        "copier_version": "9.18.1",
        "created_at": STAMP,
        "updated_at": STAMP,
        "root_template": "app@1.0.0",
        "layers": [_layer("core"), _layer("service")],
        **overrides,
    }


class TestBoilerplateLockHappyPath:
    """A lock records the layers of the last complete operation, in order."""

    def test_defaults_to_the_namespaced_schema_version(self) -> None:
        lock = BoilerplateLock.model_validate(_fields())

        assert lock.schema_version == LOCK_SCHEMA_VERSION == "boilerplate/lock@1"

    def test_keeps_the_layers_in_execution_order(self) -> None:
        lock = BoilerplateLock.model_validate(_fields())

        assert [layer.name for layer in lock.layers] == ["core", "service"]

    def test_the_answers_file_hashes_are_optional(self) -> None:
        assert (
            BoilerplateLock.model_validate(_fields()).copier_answers_file_hashes is None
        )

    def test_accepts_hashes_keyed_by_layer_name(self) -> None:
        lock = BoilerplateLock.model_validate(
            _fields(copier_answers_file_hashes={"core": HASH, "service": HASH})
        )

        assert lock.copier_answers_file_hashes == {"core": HASH, "service": HASH}

    @pytest.mark.parametrize("schema", ["boilerplate/lock@1", "boilerplate/lock@1.4"])
    def test_accepts_any_minor_of_the_supported_major(self, schema: str) -> None:
        assert BoilerplateLock.model_validate(_fields(schema_version=schema))

    def test_ignores_fields_a_later_minor_schema_adds(self) -> None:
        assert BoilerplateLock.model_validate(_fields(added_later=1))

    def test_serializes_timestamps_as_iso_8601_utc(self) -> None:
        dumped = BoilerplateLock.model_validate(_fields()).model_dump(mode="json")

        assert dumped["created_at"] == "2026-10-08T12:00:00Z"


class TestBoilerplateLockSadPath:
    """A lock that breaks the schema's invariants is refused."""

    @pytest.mark.parametrize(
        "schema", ["boilerplate/environment@1", "lock@1", "boilerplate/lock@0", "1"]
    )
    def test_rejects_a_schema_version_that_is_not_the_supported_major(
        self, schema: str
    ) -> None:
        with pytest.raises(ValidationError):
            BoilerplateLock.model_validate(_fields(schema_version=schema))

    def test_rejects_a_naive_timestamp(self) -> None:
        with pytest.raises(ValidationError):
            BoilerplateLock.model_validate(
                _fields(created_at=datetime(2026, 10, 8, 12, 0))  # noqa: DTZ001
            )

    def test_rejects_a_lock_with_no_layers(self) -> None:
        """Hold at least one layer: the root, which every operation reads."""
        with pytest.raises(ValidationError, match="layers"):
            BoilerplateLock.model_validate(_fields(layers=[]))

    def test_rejects_a_lock_that_leaves_the_layers_out(self) -> None:
        fields = _fields()
        del fields["layers"]

        with pytest.raises(ValidationError, match="layers"):
            BoilerplateLock.model_validate(fields)

    def test_rejects_two_layers_of_one_name(self) -> None:
        with pytest.raises(ValidationError, match="core"):
            BoilerplateLock.model_validate(
                _fields(layers=[_layer("core"), _layer("core", "1.1.0")])
            )

    def test_rejects_a_hash_for_a_layer_the_lock_does_not_list(self) -> None:
        with pytest.raises(ValidationError, match="ghost"):
            BoilerplateLock.model_validate(
                _fields(copier_answers_file_hashes={"ghost": HASH})
            )

    def test_rejects_a_hash_that_is_not_a_sha_256_digest(self) -> None:
        with pytest.raises(ValidationError):
            BoilerplateLock.model_validate(
                _fields(copier_answers_file_hashes={"core": "sha256:" + HASH})
            )

    def test_is_immutable(self) -> None:
        lock = BoilerplateLock.model_validate(_fields())

        with pytest.raises(ValidationError):
            lock.root_template = "other@1.0.0"
