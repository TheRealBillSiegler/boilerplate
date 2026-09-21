"""Behavior-driven tests for TemplateInfo model in template system workflows."""

from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import ValidationError

from boilerplate.integrations.copier_types import Template as CopierTemplate
from boilerplate.models import TemplateInfo


# Test fixtures for common scenarios
@pytest.fixture
def simple_template(template_factory: Callable[..., TemplateInfo]) -> TemplateInfo:
    """Provide a basic template for testing core functionality."""
    return template_factory("simple", "1.0.0", description="A simple template")


@pytest.fixture
def complex_template(template_factory: Callable[..., TemplateInfo]) -> TemplateInfo:
    """Provide a complex template with dependencies for testing advanced scenarios."""
    return template_factory(
        "webapp",
        "2.1.0",
        description="Full-stack web application",
        extends=["base@1.5.0", "auth@1.2.0"],
    )


@pytest.fixture
def copier_template() -> CopierTemplate:
    """Provide a minimal CopierTemplate for validation tests."""
    return CopierTemplate(str(Path()))


class TestTemplateIdentification:
    """Tests how TemplateInfo identifies and represents templates in the system."""

    @pytest.mark.parametrize(
        "name,version,description,expected_specifier",
        [
            ("demo", "1.0.0", "Demo template", "demo@1.0.0"),
            ("project-base", "2.1.0", "Project base", "project-base@2.1.0"),
            ("my_template", "0.1.0-alpha", "Alpha template", "my_template@0.1.0a0"),
        ],
        ids=["simple", "with-dash", "with-prerelease"],
    )
    def test_template_provides_complete_identity_information(
        self,
        template_factory: Callable[..., TemplateInfo],
        name: str,
        version: str,
        description: str,
        expected_specifier: str,
    ) -> None:
        """TemplateInfo provides complete identification for discovered templates.

        When the system discovers a template, TemplateInfo supplies all
        necessary identification information.
        """
        template = template_factory(name, version, description=description)

        # The template should provide its essential identification
        assert template.name == name, f"Expected name {name}, got {template.name}"
        assert template.meta.description == description, (
            f"Expected description {description}"
        )
        # Template location should contain the template name (but may include
        # worker ID for parallel execution)
        assert name in str(template.location), (
            f"Expected location to contain {name}, got {template.location}"
        )
        assert isinstance(template.copier_template, CopierTemplate), (
            "Should provide CopierTemplate"
        )

        # The computed specifier should combine name and version for
        # unique identification
        assert str(template.specifier) == expected_specifier, (
            f"Expected specifier {expected_specifier}, got {template.specifier}"
        )
        assert template.specifier.name == name, f"Specifier name should be {name}"

    def test_templates_with_identical_content_are_equal(
        self, simple_template: TemplateInfo
    ) -> None:
        """When two TemplateInfo instances have identical content, they are equal."""
        # Create another template with identical content
        template2 = TemplateInfo(
            name=simple_template.name,
            meta=simple_template.meta,
            location=simple_template.location,
            copier_template=simple_template.copier_template,
        )

        assert simple_template == template2, "Identical templates should be equal"
        # Note: TemplateInfo is not hashable by design since it's
        # a mutable Pydantic model
        assert repr(simple_template), (
            "Template should have meaningful string representation"
        )

    def test_templates_with_different_content_are_not_equal(
        self, simple_template: TemplateInfo, complex_template: TemplateInfo
    ) -> None:
        """Templates with different names, versions, or metadata are not equal."""
        assert simple_template != complex_template, (
            "Different templates should not be equal"
        )
        assert simple_template.specifier != complex_template.specifier, (
            "Should have different specifiers"
        )


class TestTemplateSystemIntegration:
    """Tests how TemplateInfo integrates with template system workflows."""

    @pytest.mark.parametrize(
        "name,version,description",
        [
            ("project", "2.1.0", "Project template"),
            ("api", "1.0.0", "API template"),
            ("web-app", "3.0.0b0", "Web application"),  # Use normalized beta format
        ],
        ids=["project", "api", "beta-version"],
    )
    def test_template_can_be_used_for_registry_operations(
        self,
        template_factory: Callable[..., TemplateInfo],
        name: str,
        version: str,
        description: str,
    ) -> None:
        """TemplateInfo provides data necessary for registry operations."""
        template = template_factory(name, version, description=description)

        # Registry operations need these properties
        registry_tag = f"{template.name}@{template.meta.version}"
        expected_tag = f"{name}@{version}"
        assert registry_tag == expected_tag, f"Expected registry tag {expected_tag}"

        # Display operations need these properties
        display_data = (
            template.name,
            str(template.meta.version),
            template.meta.description,
            str(template.location),
        )
        # Template location should contain the name (but may include
        # worker ID for parallel execution)
        assert display_data[0] == name, f"Expected name {name}, got {display_data[0]}"
        assert display_data[1] == version, (
            f"Expected version {version}, got {display_data[1]}"
        )
        assert display_data[2] == description, (
            f"Expected description {description}, got {display_data[2]}"
        )
        assert name in display_data[3], (
            f"Expected location to contain {name}, got {display_data[3]}"
        )

    def test_template_specifier_enables_dependency_resolution(
        self, template_factory: Callable[..., TemplateInfo]
    ) -> None:
        """Specifiers provide standardized template identification for dependencies."""
        base_template = template_factory("base", "1.5.0")
        extending_template = template_factory("webapp", "2.0.0", extends=["base@1.5.0"])

        # Dependency chains use specifiers for resolution
        assert str(base_template.specifier) == "base@1.5.0", (
            "Base template should have correct specifier"
        )
        assert extending_template.meta.extends == ["base@1.5.0"], (
            "Should preserve dependency references"
        )

        # Templates can be compared and sorted by specifier
        assert base_template.specifier != extending_template.specifier, (
            "Different templates have different specifiers"
        )

    def test_templates_can_be_sorted_by_specifier(
        self, template_factory: Callable[..., TemplateInfo]
    ) -> None:
        """Templates can be sorted by their specifiers for consistent ordering."""
        templates = [
            template_factory("zebra", "1.0.0"),
            template_factory("alpha", "2.0.0"),
            template_factory("alpha", "1.0.0"),
        ]

        sorted_templates = sorted(templates, key=lambda t: t.specifier)
        expected_order = ["alpha@1.0.0", "alpha@2.0.0", "zebra@1.0.0"]
        actual_order = [str(t.specifier) for t in sorted_templates]

        assert actual_order == expected_order, (
            f"Expected order {expected_order}, got {actual_order}"
        )


class TestTemplateValidation:
    """Tests template validation behaviors that protect system integrity."""

    @pytest.mark.parametrize(
        "invalid_meta,expected_error_pattern",
        [
            ("not-metadata", "Input should be a valid dictionary"),
            (123, "Input should be a valid dictionary"),
            (None, "Input should be a valid dictionary"),
            ([], "Input should be a valid dictionary"),
        ],
        ids=["string", "number", "none", "list"],
    )
    def test_system_rejects_malformed_template_metadata(
        self,
        copier_template: CopierTemplate,
        invalid_meta: str,
        expected_error_pattern: str,
    ) -> None:
        """Invalid template metadata is rejected with clear errors."""
        with pytest.raises(ValidationError, match=expected_error_pattern):
            TemplateInfo(
                name="invalid-template",
                meta=invalid_meta,  # pyright: ignore[reportArgumentType]
                location=Path(),
                copier_template=copier_template,
            )  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "invalid_location,expected_error_pattern",
        [
            (12345, "Input is not a valid path"),
            (None, "Input is not a valid path"),
            ([], "Input is not a valid path"),
        ],
        ids=["number", "none", "list"],
    )
    def test_system_rejects_invalid_location_paths(
        self,
        template_factory: Callable[..., TemplateInfo],
        copier_template: CopierTemplate,
        invalid_location: int,
        expected_error_pattern: str,
    ) -> None:
        """When template location is invalid, the system rejects it."""
        meta = template_factory("demo-template", description="desc").meta

        with pytest.raises(ValidationError, match=expected_error_pattern):
            TemplateInfo(
                name="demo-template",
                meta=meta,
                location=invalid_location,  # pyright: ignore[reportArgumentType]
                copier_template=copier_template,
            )  # type: ignore[arg-type]

    def test_system_accepts_string_paths_as_locations(
        self,
        template_factory: Callable[..., TemplateInfo],
        copier_template: CopierTemplate,
    ) -> None:
        """String paths are automatically converted to Path objects."""
        meta = template_factory("demo-template", description="desc").meta

        # This should work - Pydantic converts strings to Path objects
        template = TemplateInfo(
            name="demo-template",
            meta=meta,
            location="not-a-path-object",  # pyright: ignore[reportArgumentType]
            copier_template=copier_template,
        )

        assert isinstance(template.location, Path), "String should be converted to Path"
        assert str(template.location) == "not-a-path-object"

    def test_system_requires_all_essential_fields(self) -> None:
        """TemplateInfo requires all essential fields for proper system operation."""
        meta = TemplateInfo.__annotations__.keys()
        required_fields = {"name", "meta", "location", "copier_template"}

        assert required_fields.issubset(meta), (
            f"Missing required fields: {required_fields - meta}"
        )
