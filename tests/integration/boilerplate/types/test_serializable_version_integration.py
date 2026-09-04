"""Integration tests for SerializableVersion in real-world scenarios."""

import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from boilerplate.models.template_meta import TemplateMeta
from boilerplate.types import SerializableVersion


class ApiResponse(BaseModel):
    """Mock API response model for testing."""

    template_name: str
    current_version: SerializableVersion
    available_versions: list[SerializableVersion]


class TestTemplateVersionCompatibility:
    """Tests version behavior in template compatibility scenarios."""

    @pytest.fixture
    def sample_templates(self) -> dict[str, TemplateMeta]:
        """Sample template metadata for compatibility testing."""
        return {
            "base": TemplateMeta(
                name="base-template",
                description="Base template for projects",
                version=SerializableVersion("2.0.0"),
            ),
            "feature": TemplateMeta(
                name="feature-template",
                description="Feature extension template",
                version=SerializableVersion("1.5.0"),
                extends=["base-template"],
            ),
            "advanced": TemplateMeta(
                name="advanced-template",
                description="Advanced template with modern features",
                version=SerializableVersion("3.0.0b1"),
                extends=["base-template", "feature-template"],
            ),
        }

    def test_determines_template_compatibility_using_version_comparison(
        self, sample_templates: dict[str, TemplateMeta]
    ) -> None:
        """Determines template compatibility based on version comparisons."""
        base = sample_templates["base"]
        feature = sample_templates["feature"]
        advanced = sample_templates["advanced"]

        # Advanced template extends both base and feature
        assert "base-template" in advanced.extends
        assert "feature-template" in advanced.extends

        # Version ordering should make sense for template evolution
        assert advanced.version > base.version > feature.version

    def test_identifies_incompatible_template_versions(
        self, sample_templates: dict[str, TemplateMeta]
    ) -> None:
        """Identifies when template versions create logical inconsistencies."""
        # Create an old base template that would be incompatible
        old_base = TemplateMeta(
            name="base-template",
            description="Outdated base template",
            version=SerializableVersion("1.0.0"),
        )

        advanced = sample_templates["advanced"]

        # Advanced template expects newer base versions via extends relationship
        assert "base-template" in advanced.extends
        assert old_base.version < advanced.version, (
            "Old base version should be older than advanced template"
        )

    def test_handles_prerelease_version_compatibility(
        self, sample_templates: dict[str, TemplateMeta]
    ) -> None:
        """Handles pre-release versions in compatibility checks."""
        beta_template = TemplateMeta(
            name="beta-template",
            description="Beta version template",
            version=SerializableVersion("2.0.0b1"),
            extends=["feature-template"],
        )

        feature = sample_templates["feature"]

        # Beta version should be newer than stable feature version
        assert beta_template.version > feature.version
        assert "feature-template" in beta_template.extends


class TestConfigurationFilePersistence:
    """Tests reading and writing version data in configuration files."""

    def test_preserves_versions_through_yaml_round_trip(self, tmp_path: Path) -> None:
        """Maintains version precision through YAML file round-trips."""
        config_file = tmp_path / "template.yml"
        original_metadata = TemplateMeta(
            name="test-template",
            description="Test template for version persistence",
            version=SerializableVersion("1.2.3b4+local.build"),
        )

        # Write to YAML using TemplateMeta's dump method
        original_metadata.dump(config_file)

        # Read back from YAML using TemplateMeta's load method
        restored_metadata = TemplateMeta.load(config_file)

        assert str(restored_metadata.version) == "1.2.3b4+local.build"
        assert restored_metadata.name == "test-template"
        assert restored_metadata.description == "Test template for version persistence"

    def test_handles_version_updates_in_configuration_files(
        self, tmp_path: Path
    ) -> None:
        """Supports updating versions in configuration files."""
        config_file = tmp_path / "template.yml"

        # Create initial template
        initial_template = TemplateMeta(
            name="evolving-template",
            description="Template that can be updated",
            version=SerializableVersion("1.0.0"),
        )
        initial_template.dump(config_file)

        # Load and update
        metadata = TemplateMeta.load(config_file)

        # Simulate version bump
        updated_metadata = TemplateMeta(
            name=metadata.name,
            description=metadata.description,
            version=SerializableVersion("1.1.0"),
            extends=metadata.extends,
            schema_version=metadata.schema_version,
        )

        # Write updated version
        updated_metadata.dump(config_file, overwrite=True)

        # Verify update
        final_metadata = TemplateMeta.load(config_file)
        assert str(final_metadata.version) == "1.1.0"
        assert final_metadata.name == "evolving-template"


class TestApiRequestResponseCycles:
    """Tests version handling in API request/response scenarios."""

    def test_processes_api_responses_with_multiple_versions(self) -> None:
        """Handles API responses containing lists of versions."""
        api_json = {
            "template_name": "popular-template",
            "current_version": "2.1.0",
            "available_versions": ["1.0.0", "1.5.0", "2.0.0", "2.1.0", "2.2.0b1"],
        }

        response = ApiResponse.model_validate(api_json)

        # Verify all versions are properly parsed
        assert str(response.current_version) == "2.1.0"
        assert len(response.available_versions) == 5

        # Verify version ordering
        versions = response.available_versions
        assert versions[0] < versions[1] < versions[2] < versions[3]
        assert versions[3] < versions[4]  # 2.1.0 < 2.2.0b1

    def test_generates_api_compatible_json_responses(self) -> None:
        """Generates JSON that's compatible with external API consumers."""
        response = ApiResponse(
            template_name="integration-template",
            current_version=SerializableVersion("1.0.0"),
            available_versions=[
                SerializableVersion("0.9.0"),
                SerializableVersion("1.0.0"),
                SerializableVersion("1.1.0a1"),
            ],
        )

        json_output = response.model_dump_json()
        parsed = json.loads(json_output)

        # Verify JSON structure for API consumers
        assert parsed["current_version"] == "1.0.0"
        assert parsed["available_versions"] == ["0.9.0", "1.0.0", "1.1.0a1"]

    def test_handles_api_error_scenarios_with_invalid_versions(self) -> None:
        """Gracefully handles API responses with invalid version data."""
        invalid_api_json = {
            "template_name": "broken-template",
            "current_version": "not.a.version",
            "available_versions": ["1.0.0"],
        }

        with pytest.raises(ValueError, match="Invalid version"):
            ApiResponse.model_validate(invalid_api_json)


class TestVersionBasedFeatureFlags:
    """Tests version-based feature enabling and compatibility."""

    def test_enables_features_based_on_version_thresholds(self) -> None:
        """Enables features when version meets minimum requirements."""
        template_v2 = TemplateMeta(
            name="modern-template",
            version=SerializableVersion("2.0.0"),
        )

        # Feature requires version >= 1.5.0
        feature_min_version = SerializableVersion("1.5.0")
        assert template_v2.version >= feature_min_version, (
            "Template v2.0.0 should support features requiring v1.5.0+"
        )

    def test_disables_features_for_older_versions(self) -> None:
        """Disables features when version is below requirements."""
        legacy_template = TemplateMeta(
            name="legacy-template",
            version=SerializableVersion("1.0.0"),
        )

        # Feature requires version >= 1.5.0
        feature_min_version = SerializableVersion("1.5.0")
        assert legacy_template.version < feature_min_version, (
            "Legacy template should not support features requiring v1.5.0+"
        )

    def test_handles_prerelease_versions_in_feature_detection(self) -> None:
        """Properly handles pre-release versions for feature flags."""
        beta_template = TemplateMeta(
            name="beta-template",
            version=SerializableVersion("2.0.0b1"),
        )

        # Beta versions should be less than final releases
        final_version = SerializableVersion("2.0.0")
        assert beta_template.version < final_version, (
            "Beta version should be less than final release"
        )

        # But greater than previous stable releases
        previous_stable = SerializableVersion("1.9.0")
        assert beta_template.version > previous_stable, (
            "Beta version should be greater than previous stable"
        )
