"""Tests for SerializableVersion, a PEP 440-compliant JSON-serializable version type."""

import json

import pytest
from packaging.version import InvalidVersion
from packaging.version import Version as BaseVersion
from pydantic import BaseModel, ValidationError

from boilerplate.types import SerializableVersion


class VersionModel(BaseModel):
    version: SerializableVersion


class TestVersionCreation:
    """Tests that versions can be created from various valid inputs."""

    @pytest.mark.parametrize(
        "version_string",
        [
            "1.0.0",
            "2.1.3b2",
            "0.1.post1",
            "1.0.0a1",
            "1.0.0rc1",
            "1.0.0.dev0",
            "1!2.0.0",  # epoch
            "1.0.0+local.version",  # local version
            "1.0.0a1.dev456+sha.abc123",  # complex version
        ],
        ids=[
            "stable",
            "beta",
            "post-release",
            "alpha",
            "release-candidate",
            "dev",
            "epoch",
            "local-version",
            "complex",
        ],
    )
    def test_accepts_valid_pep440_version_strings(self, version_string: str) -> None:
        """Accepts all valid PEP 440 version formats."""
        version = SerializableVersion(version_string)
        assert str(version) == version_string

    @pytest.mark.parametrize(
        "invalid_input",
        ["", "not.a.version", "1..0"],
        ids=["empty", "non-numeric", "double-dot"],
    )
    def test_rejects_invalid_version_strings_directly(self, invalid_input: str) -> None:
        """Rejects invalid versions with InvalidVersion exception."""
        with pytest.raises(InvalidVersion, match=r"Invalid version:"):
            SerializableVersion(invalid_input)


class TestVersionComparison:
    """Tests that versions compare correctly according to PEP 440 rules."""

    @pytest.mark.parametrize(
        "lower_version,higher_version",
        [
            ("1.0.0", "1.0.1"),
            ("1.0.0", "1.1.0"),
            ("1.0.0", "2.0.0"),
            ("1.0.0a1", "1.0.0a2"),
            ("1.0.0a1", "1.0.0b1"),
            ("1.0.0b1", "1.0.0rc1"),
            ("1.0.0rc1", "1.0.0"),
            ("1.0.0", "1.0.0.post1"),
            ("1.0.0.dev1", "1.0.0"),
            ("0!1.0.0", "1!1.0.0"),  # epoch comparison
        ],
        ids=[
            "patch-increment",
            "minor-increment",
            "major-increment",
            "alpha-sequence",
            "alpha-to-beta",
            "beta-to-rc",
            "rc-to-final",
            "final-to-post",
            "dev-to-final",
            "epoch-increment",
        ],
    )
    def test_version_ordering_follows_pep440_rules(
        self, lower_version: str, higher_version: str
    ) -> None:
        """Orders versions according to PEP 440 precedence rules."""
        v1 = SerializableVersion(lower_version)
        v2 = SerializableVersion(higher_version)

        assert v1 < v2, f"{lower_version} should be less than {higher_version}"
        assert v2 > v1, f"{higher_version} should be greater than {lower_version}"
        assert v1 != v2, "Versions should not be equal"

    def test_identical_versions_are_equal(self) -> None:
        """Treats identical version strings as equal."""
        v1 = SerializableVersion("1.2.3")
        v2 = SerializableVersion("1.2.3")

        assert v1 == v2
        assert not (v1 < v2)
        assert not (v1 > v2)


class TestPydanticIntegration:
    """Tests Pydantic field behavior and validation."""

    def test_validates_and_preserves_version_in_pydantic_model(self) -> None:
        """Works as a Pydantic field with proper validation."""
        model = VersionModel.model_validate({"version": "1.2.3"})

        assert isinstance(model.version, SerializableVersion)
        assert str(model.version) == "1.2.3"

    def test_accepts_different_input_types_through_pydantic(self) -> None:
        """Accepts various input types when used as Pydantic field."""
        # String input
        model1 = VersionModel.model_validate({"version": "1.0.0"})
        assert str(model1.version) == "1.0.0"

        # SerializableVersion input (through Pydantic validation)
        version = SerializableVersion("2.0.0")
        model2 = VersionModel.model_validate({"version": version})
        assert model2.version is version

        # BaseVersion input (through Pydantic validation)
        base_version = BaseVersion("3.0.0")
        model3 = VersionModel.model_validate({"version": base_version})
        assert str(model3.version) == "3.0.0"

    def test_raises_validation_error_for_invalid_versions_in_pydantic(self) -> None:
        """Raises ValidationError for invalid versions in Pydantic models."""
        with pytest.raises(ValidationError) as exc_info:
            VersionModel.model_validate({"version": "invalid.version"})

        error = exc_info.value.errors()[0]
        assert error["type"] == "value_error"
        assert "Invalid version" in str(error.get("ctx", {}).get("error", ""))


class TestJsonSerialization:
    """Tests JSON serialization and schema generation."""

    def test_serializes_to_version_string_in_json(self) -> None:
        """Serializes as a plain version string in JSON output."""
        model = VersionModel.model_validate({"version": "1.0.0a1"})
        json_data = model.model_dump_json()

        # Parse back to verify structure
        parsed = json.loads(json_data)
        assert parsed["version"] == "1.0.0a1"

    def test_round_trip_json_serialization_preserves_version(self) -> None:
        """Maintains version accuracy through JSON round-trip."""
        original_version = "2.1.3b2+local.build"
        model = VersionModel.model_validate({"version": original_version})

        # Serialize to JSON and back
        json_data = model.model_dump_json()
        restored = VersionModel.model_validate_json(json_data)

        assert str(restored.version) == original_version

    def test_generates_proper_json_schema_for_api_docs(self) -> None:
        """Generates useful JSON schema for OpenAPI documentation."""
        schema = VersionModel.model_json_schema()
        version_schema = schema["properties"]["version"]

        assert version_schema["type"] == "string"
        assert version_schema["format"] == "version"
        assert "description" in version_schema
        assert "examples" in version_schema
        assert len(version_schema["examples"]) > 0
