"""Integration tests for TemplateMeta file I/O and real template validation."""

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from boilerplate.models import TemplateMeta
from boilerplate.types import SerializableVersion


class TestTemplateMetaFileOperations:
    """Integration tests for file I/O operations with real filesystem behavior."""

    def test_loads_complete_metadata_from_yaml_file(self, tmp_path: Path) -> None:
        """Loads all metadata fields from a valid YAML file."""
        yaml_path = tmp_path / "boilerplate.yml"
        yaml_path.write_text(
            """
            schema_version: 1.0
            name: test-template
            description: Test description
            version: 1.2.3
            extends:
              - base-template
            """,
            encoding="utf-8",
        )
        meta = TemplateMeta.load(tmp_path)

        assert meta.schema_version == SerializableVersion("1.0")
        assert meta.name == "test-template"
        assert meta.description == "Test description"
        assert meta.version == SerializableVersion("1.2.3")
        assert meta.extends == ["base-template"]

    def test_loads_from_directory_containing_yaml_file(self, tmp_path: Path) -> None:
        """Finds and loads boilerplate.yml when given a directory path."""
        yaml_path = tmp_path / "boilerplate.yml"
        yaml_path.write_text(
            """
            name: directory-template
            version: 2.0.0
            """,
            encoding="utf-8",
        )
        meta = TemplateMeta.load(tmp_path)

        assert meta.name == "directory-template"
        assert meta.version == SerializableVersion("2.0.0")

    def test_loads_from_direct_yaml_file_path(self, tmp_path: Path) -> None:
        """Loads metadata when given direct path to YAML file."""
        yaml_path = tmp_path / "custom-name.yml"
        yaml_path.write_text(
            """
            name: custom-file-template
            version: 3.0.0
            """,
            encoding="utf-8",
        )
        meta = TemplateMeta.load(yaml_path)

        assert meta.name == "custom-file-template"
        assert meta.version == SerializableVersion("3.0.0")

    def test_saves_metadata_to_yaml_file_with_proper_formatting(
        self, tmp_path: Path
    ) -> None:
        """Saves metadata to YAML file with correct structure and values."""
        path = tmp_path / "test_boilerplate_dump.yml"
        meta = TemplateMeta.model_validate(
            {
                "schema_version": "1.0",
                "name": "test-template",
                "description": "Dumped description",
                "version": "1.2.3",
                "extends": ["base-template"],
            }
        )
        meta.dump(path, overwrite=True)

        loaded_data = path.read_text(encoding="utf-8")
        assert "schema_version: '1.0'" in loaded_data
        assert "name: test-template" in loaded_data
        assert "version: 1.2.3" in loaded_data
        assert "description: Dumped description" in loaded_data
        assert "extends:" in loaded_data

    def test_creates_parent_directories_when_dumping(self, tmp_path: Path) -> None:
        """Creates missing parent directories when saving to nested path."""
        nested_path = tmp_path / "deep" / "nested" / "path" / "boilerplate.yml"

        meta = TemplateMeta.model_validate(
            {
                "name": "nested-template",
                "version": "1.0.0",
            }
        )

        meta.dump(nested_path, overwrite=True)

        assert nested_path.exists()
        content = nested_path.read_text(encoding="utf-8")
        assert "name: nested-template" in content

    def test_preserves_data_through_save_load_cycle(self, tmp_path: Path) -> None:
        """Maintains all data when saving and loading back."""
        original_data = {
            "schema_version": "1.0",
            "name": "round-trip-template",
            "description": "Test round-trip with üñíçødé characters",
            "version": "2.1.3",
            "extends": ["parent-1", "parent-2"],
        }

        # Create original metadata
        original_meta = TemplateMeta.model_validate(original_data)

        # Save to file
        save_path = tmp_path / "round_trip.yml"
        original_meta.dump(save_path)

        # Load back from file
        loaded_meta = TemplateMeta.load(save_path)

        # Verify all fields are preserved
        assert loaded_meta.schema_version == original_meta.schema_version
        assert loaded_meta.name == original_meta.name
        assert loaded_meta.description == original_meta.description
        assert loaded_meta.version == original_meta.version
        assert loaded_meta.extends == original_meta.extends

        # Verify they're equivalent when serialized
        assert loaded_meta.model_dump() == original_meta.model_dump()

    def test_handles_unicode_content_correctly(self, tmp_path: Path) -> None:
        """Properly handles Unicode characters in all text fields."""
        yaml_path = tmp_path / "boilerplate.yml"
        # Use ASCII-compatible Unicode characters that work with default encoding
        yaml_path.write_text(
            """
            name: test-template-unicode
            description: "A test template with simple unicode: café résumé"
            version: 1.0.0
            extends:
              - base-template
            """,
            encoding="utf-8",
        )

        meta = TemplateMeta.load(tmp_path)
        assert meta.name == "test-template-unicode"
        assert "café résumé" in meta.description
        assert meta.extends == ["base-template"]


class TestRealTemplateValidation:
    """Integration tests using actual template files from the codebase."""

    def test_loads_project_template_successfully(self) -> None:
        """Successfully loads the project template boilerplate.yml."""
        project_template_path = (
            Path(__file__).parent.parent.parent.parent.parent
            / "src"
            / "boilerplate"
            / "templates"
            / "project"
        )

        meta = TemplateMeta.load(project_template_path)

        assert meta.name == "project"
        assert meta.version == SerializableVersion("0.3.0")
        assert meta.description == "A suitable base for any Python project."
        assert meta.extends == []  # Project template has no extensions

    def test_loads_streamlit_template_successfully(self) -> None:
        """Successfully loads the streamlit template boilerplate.yml."""
        streamlit_template_path = (
            Path(__file__).parent.parent.parent.parent.parent
            / "src"
            / "boilerplate"
            / "templates"
            / "streamlit"
        )

        meta = TemplateMeta.load(streamlit_template_path)

        assert meta.name == "streamlit"
        assert meta.version == SerializableVersion("0.2.0")
        assert meta.description == "Streamlit boilerplate for data applications"
        assert meta.extends == ["project"]  # Streamlit extends project

    def test_all_template_files_are_valid(self) -> None:
        """Validates that all template boilerplate.yml files are valid."""
        templates_dir = (
            Path(__file__).parent.parent.parent.parent.parent
            / "src"
            / "boilerplate"
            / "templates"
        )

        boilerplate_files = list(templates_dir.rglob("boilerplate.yml"))
        assert len(boilerplate_files) > 0, "No boilerplate.yml files found"

        valid_templates = []
        for boilerplate_file in boilerplate_files:
            try:
                meta = TemplateMeta.load(boilerplate_file)
                valid_templates.append((boilerplate_file.parent.name, meta))
            except Exception as e:
                pytest.fail(f"Failed to load {boilerplate_file}: {e}")

        # Verify we loaded at least the known templates
        template_names = {name for name, _ in valid_templates}
        assert "project" in template_names
        assert "streamlit" in template_names

        # Verify all have required fields
        for name, meta in valid_templates:
            assert meta.name, f"Template {name} missing name"
            assert meta.version, f"Template {name} missing version"

    def test_template_hierarchy_is_valid(self) -> None:
        """Validates that template extension hierarchy makes sense."""
        templates_dir = (
            Path(__file__).parent.parent.parent.parent.parent
            / "src"
            / "boilerplate"
            / "templates"
        )

        # Load all templates and build dependency graph
        templates = {}
        for boilerplate_file in templates_dir.rglob("boilerplate.yml"):
            meta = TemplateMeta.load(boilerplate_file)
            templates[meta.name] = meta

        # Verify extension references are valid
        for template_name, meta in templates.items():
            for extended_template in meta.extends:
                assert extended_template in templates, (
                    f"Template '{template_name}' extends '{extended_template}' "
                    f"but '{extended_template}' template not found"
                )


class TestFileSystemErrorHandling:
    """Integration tests for file system error scenarios."""

    def test_raises_file_not_found_when_yaml_missing(self, tmp_path: Path) -> None:
        """Raises FileNotFoundError when boilerplate.yml doesn't exist."""
        non_existent_dir = tmp_path / "missing"
        with pytest.raises(FileNotFoundError):
            TemplateMeta.load(non_existent_dir)

    def test_raises_file_not_found_for_missing_file(self, tmp_path: Path) -> None:
        """Raises FileNotFoundError when direct file path doesn't exist."""
        missing_file = tmp_path / "missing.yml"
        with pytest.raises(FileNotFoundError):
            TemplateMeta.load(missing_file)

    @pytest.mark.parametrize(
        "malformed_content",
        [
            "{ invalid yaml syntax",  # Invalid YAML syntax
            "name: test\nversion: 1.0.0\n  invalid_indent:",  # Invalid indentation
            "name: test\nversion: [\n",  # Incomplete YAML
        ],
    )
    def test_handles_malformed_yaml_gracefully(
        self, tmp_path: Path, malformed_content: str
    ) -> None:
        """Provides clear error when YAML syntax is invalid."""
        yaml_path = tmp_path / "boilerplate.yml"
        yaml_path.write_text(malformed_content, encoding="utf-8")

        with pytest.raises((yaml.YAMLError, ValidationError)):
            TemplateMeta.load(tmp_path)

    @pytest.mark.parametrize(
        "yaml_content",
        [
            "",  # Empty file
            "# Just a comment",  # Only comments
            "null",  # Null content
            "{}",  # Empty dict
        ],
    )
    def test_handles_empty_or_minimal_yaml_files(
        self, tmp_path: Path, yaml_content: str
    ) -> None:
        """Handles edge cases of empty or minimal YAML content."""
        yaml_path = tmp_path / "boilerplate.yml"
        yaml_path.write_text(yaml_content, encoding="utf-8")

        # These should fail validation due to missing required fields
        with pytest.raises(ValidationError, match=r"(name|version)"):
            TemplateMeta.load(tmp_path)


def test_template_meta_round_trip(tmp_path: Path) -> None:
    """Ensures TemplateMeta can be serialized and deserialized losslessly."""
    original = TemplateMeta.model_validate(
        {
            "schema_version": "1.0",
            "name": "my-template",
            "description": "Integration test description",
            "version": "1.0.0",
            "extends": ["base-template"],
        }
    )

    path = tmp_path / "boilerplate.yml"
    original.dump(path)

    loaded = TemplateMeta.load(path)

    # Validate object equality through serialization
    assert loaded.model_dump() == original.model_dump()

    # Confirm specific field preservation
    assert loaded.schema_version == original.schema_version
    assert loaded.name == original.name
    assert loaded.description == original.description
    assert loaded.version == original.version
    assert loaded.extends == original.extends
