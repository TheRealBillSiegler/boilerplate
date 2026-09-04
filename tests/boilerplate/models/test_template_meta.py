"""Tests for the TemplateMeta model in template_meta.py."""

from collections.abc import Callable
from pathlib import Path

import pytest
from packaging.version import Version
from pydantic import ValidationError

from boilerplate.models import SCHEMA_VERSION, TemplateMeta
from boilerplate.models.template_info import TemplateInfo
from boilerplate.types import SerializableVersion


class TestTemplateMetaValidation:
    """Template metadata validates required fields and format constraints."""

    def test_accepts_complete_valid_metadata(
        self, template_factory: Callable[..., TemplateInfo]
    ) -> None:
        """Accepts template metadata with all required fields."""
        template = template_factory(
            "test-template",
            "1.2.3",
            description="A test template.",
            extends=["base-template"],
        )
        meta = template.meta

        assert meta.schema_version == SCHEMA_VERSION
        assert meta.name == "test-template"
        assert meta.description == "A test template."
        assert meta.version == SerializableVersion("1.2.3")
        assert meta.extends == ["base-template"]

    def test_accepts_minimal_valid_metadata(
        self, template_factory: Callable[..., TemplateInfo]
    ) -> None:
        """Accepts template metadata with only required fields."""
        template = template_factory("minimal-template", "1.0.0", description="")
        meta = template.meta

        assert meta.name == "minimal-template"
        assert meta.version == SerializableVersion("1.0.0")
        assert meta.description == ""  # Default empty description
        assert meta.extends == []  # Default empty extends list

    def test_rejects_missing_required_name(
        self,
    ) -> None:
        """Rejects metadata without required name field."""
        with pytest.raises(ValidationError, match="name"):
            # Try to create a TemplateMeta with validation data missing name
            data = {
                "version": "1.0.0",
            }
            TemplateMeta.model_validate(data)

    def test_rejects_missing_required_version(
        self,
    ) -> None:
        """Rejects metadata without required version field."""
        with pytest.raises(ValidationError, match="version"):
            # Try to create a TemplateMeta with validation data missing version
            data = {
                "name": "test-template",
            }
            TemplateMeta.model_validate(data)

    def test_rejects_empty_name(
        self,
    ) -> None:
        """Rejects metadata with empty name field."""
        with pytest.raises(ValidationError, match="at least 1 character"):
            # Try to create a TemplateMeta with validation data with empty name
            data = {
                "name": "",
                "version": "1.0.0",
            }
            TemplateMeta.model_validate(data)

    @pytest.mark.parametrize(
        "invalid_version",
        [
            "invalid-version",
            "",
        ],
    )
    def test_rejects_invalid_version_formats(self, invalid_version: str) -> None:
        """Rejects metadata with invalid version formats."""
        data = {
            "name": "test-template",
            "version": invalid_version,
        }
        with pytest.raises(ValidationError, match="Invalid version"):
            TemplateMeta.model_validate(data)

    def test_applies_default_schema_version_when_omitted(self) -> None:
        """Uses SCHEMA_VERSION constant when schema_version not provided."""
        data = {
            "name": "test-template",
            "version": "1.0.0",
        }
        meta = TemplateMeta.model_validate(data)
        assert meta.schema_version == SCHEMA_VERSION

    @pytest.mark.parametrize(
        "version_input,expected",
        [
            (SerializableVersion("1.2.3"), SerializableVersion("1.2.3")),
            (Version("2.0.0"), SerializableVersion("2.0.0")),
            ("3.1.4", SerializableVersion("3.1.4")),
            # Complex version formats
            ("1.0.0a1", SerializableVersion("1.0.0a1")),  # Pre-release
            ("1.0.0.post1", SerializableVersion("1.0.0.post1")),  # Post-release
            ("1.0.0.dev1", SerializableVersion("1.0.0.dev1")),  # Development
            ("2.0.0+local.1", SerializableVersion("2.0.0+local.1")),  # Local
        ],
    )
    def test_accepts_various_version_input_types(
        self, version_input: object, expected: SerializableVersion
    ) -> None:
        """Accepts and properly converts various version input types."""
        data = {
            "name": "test-template",
            "version": version_input,
        }
        meta = TemplateMeta.model_validate(data)
        assert meta.version == expected

    @pytest.mark.parametrize(
        "extends_value",
        [
            [],  # Empty list
            ["single-parent"],  # Single parent
            ["parent-1", "parent-2", "parent-3"],  # Multiple parents
        ],
    )
    def test_handles_various_extends_configurations(
        self, extends_value: list[str]
    ) -> None:
        """Properly handles different extends list configurations."""
        data = {
            "name": "test-template",
            "version": "1.0.0",
            "extends": extends_value,
        }
        meta = TemplateMeta.model_validate(data)
        assert meta.extends == extends_value


class TestTemplateMetaErrorHandling:
    """Error handling tests that focus on validation logic rather than file I/O."""

    def test_prevents_overwriting_existing_file_by_default(
        self, tmp_path: Path
    ) -> None:
        """Raises FileExistsError when overwriting without explicit permission."""
        path = tmp_path / "existing.yml"
        path.write_text("existing content")

        meta = TemplateMeta.model_validate(
            {
                "name": "test-template",
                "version": "1.0.0",
            }
        )

        with pytest.raises(FileExistsError):
            meta.dump(path, overwrite=False)

    def test_allows_overwriting_when_explicitly_requested(self, tmp_path: Path) -> None:
        """Overwrites existing file when overwrite=True is specified."""
        path = tmp_path / "overwrite-test.yml"
        path.write_text("old content")

        meta = TemplateMeta.model_validate(
            {
                "name": "new-template",
                "version": "2.0.0",
            }
        )

        meta.dump(path, overwrite=True)
        content = path.read_text()
        assert "name: new-template" in content
        assert "version: 2.0.0" in content
        assert "old content" not in content


class TestTemplateMetaLoad:
    """Tests for TemplateMeta.load's handling of on-disk boilerplate.yml content."""

    @pytest.mark.parametrize(
        "yaml_content",
        [
            "- a\n- b\n",  # Top-level sequence, not a mapping
            "just a plain string\n",  # Top-level scalar string
            "42\n",  # Top-level scalar int
        ],
    )
    def test_raises_validation_error_for_non_mapping_yaml(
        self, tmp_path: Path, yaml_content: str
    ) -> None:
        """Non-mapping YAML raises ValidationError, not TypeError.

        Regression test: boilerplate.yml content that parses to a list or
        scalar used to raise an unhandled TypeError (from an internal-only
        dict-mutation step) instead of a clean, typed ValidationError.
        """
        (tmp_path / "boilerplate.yml").write_text(yaml_content, encoding="utf-8")

        with pytest.raises(ValidationError):
            TemplateMeta.load(tmp_path)


class TestTemplateMetaFixtureIntegration:
    """Integration tests using fixtures to verify model behavior."""

    def test_validates_minimal_data_from_fixture(
        self, template_factory: Callable[..., TemplateInfo]
    ) -> None:
        """Accepts minimal valid data from fixture."""
        template = template_factory("test-template", "1.0.0")
        meta = template.meta
        assert meta.name == "test-template"
        assert meta.version == SerializableVersion("1.0.0")

    def test_validates_complete_data_from_fixture(
        self, template_factory: Callable[..., TemplateInfo]
    ) -> None:
        """Accepts complete valid data from fixture."""
        template = template_factory(
            "complete-template",
            "2.1.3",
            description="A complete test template",
            extends=["base-template", "mixin-template"],
        )
        meta = template.meta
        assert meta.name == "complete-template"
        assert meta.description == "A complete test template"
        assert len(meta.extends) == 2

    def test_loads_from_fixture_yaml_content(
        self, tmp_path: Path, template_factory: Callable[..., TemplateInfo]
    ) -> None:
        """Loads metadata from fixture YAML content."""
        # Create template using factory and write to disk
        template = template_factory(
            "sample-template",
            "1.5.0",
            description="Sample template for testing",
            extends=["parent-template"],
        )

        # Write the metadata to a temporary directory
        yaml_path = tmp_path / "boilerplate.yml"
        template.meta.dump(yaml_path)

        # Load it back and verify
        meta = TemplateMeta.load(tmp_path)
        assert meta.name == "sample-template"
        assert meta.description == "Sample template for testing"
        assert meta.version == SerializableVersion("1.5.0")

    @pytest.mark.parametrize(
        "field_to_remove",
        ["name", "version"],
    )
    def test_rejects_when_required_field_missing(self, field_to_remove: str) -> None:
        """Rejects data when any required field is missing."""
        valid_data = {
            "schema_version": "1.0",
            "name": "complete-template",
            "description": "A complete test template",
            "version": "2.1.3",
            "extends": ["base-template", "mixin-template"],
        }
        invalid_data = valid_data.copy()
        del invalid_data[field_to_remove]

        with pytest.raises(ValidationError, match=field_to_remove):
            TemplateMeta.model_validate(invalid_data)


class TestTemplateMetaEdgeCases:
    """Edge cases and boundary conditions for template metadata."""

    def test_handles_very_long_field_values(self) -> None:
        """Handles very long strings in text fields."""
        long_string = "x" * 10000  # 10K characters
        data = {
            "name": long_string,
            "description": long_string,
            "version": "1.0.0",
            "extends": [long_string],
        }

        meta = TemplateMeta.model_validate(data)
        assert len(meta.name) == 10000
        assert len(meta.description) == 10000
        assert len(meta.extends[0]) == 10000

    def test_handles_special_characters_in_names(self) -> None:
        """Handles special characters that are valid in template names."""
        special_chars_data = {
            "name": "test-template_v2.0-alpha+build.123",
            "description": "Template with @#$%^&*()+={}[]|\\:;\"'<>?,./",
            "version": "1.0.0",
        }

        meta = TemplateMeta.model_validate(special_chars_data)
        assert meta.name == "test-template_v2.0-alpha+build.123"
        assert "@#$%^&*()" in meta.description

    def test_serializes_version_consistently(self) -> None:
        """Serializes version field consistently regardless of input type."""
        test_cases = [
            {"version": "1.2.3"},
            {"version": SerializableVersion("1.2.3")},
            {"version": Version("1.2.3")},
        ]

        metas = []
        for data in test_cases:
            full_data = {"name": "test", **data}
            meta = TemplateMeta.model_validate(full_data)
            metas.append(meta)

        # All should serialize to the same string representation
        serialized_versions = [meta.model_dump()["version"] for meta in metas]
        assert len(set(serialized_versions)) == 1  # All identical
        assert serialized_versions[0] == "1.2.3"

    @pytest.mark.parametrize(
        "extends_input",
        [
            None,  # Should default to empty list
            [],  # Explicit empty list
        ],
    )
    def test_handles_missing_or_empty_extends(
        self, extends_input: list[str] | None
    ) -> None:
        """Handles missing or empty extends field gracefully."""
        data: dict[str, object] = {
            "name": "test-template",
            "version": "1.0.0",
        }
        if extends_input is not None:
            data["extends"] = extends_input

        meta = TemplateMeta.model_validate(data)
        assert meta.extends == []

    def test_model_equality_and_hashing(self) -> None:
        """Supports model equality comparisons and hashing."""
        data = {
            "name": "test-template",
            "version": "1.0.0",
            "description": "Test equality",
        }

        meta1 = TemplateMeta.model_validate(data)
        meta2 = TemplateMeta.model_validate(data.copy())

        # Same data should be equal
        assert meta1.model_dump() == meta2.model_dump()

        # Different data should not be equal
        data2 = data.copy()
        data2["name"] = "different-template"
        meta3 = TemplateMeta.model_validate(data2)

        assert meta1.model_dump() != meta3.model_dump()
