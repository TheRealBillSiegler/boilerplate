"""Tests TemplateRepository interface contract and template specifier parsing.

Tests focus on the abstract interface contract that all repository implementations
must fulfill, plus validation of the TemplateSpecifier.from_string functionality.
"""

import pytest
from packaging.version import Version
from pytest_mock import MockerFixture

from boilerplate.common.exceptions import InvalidTemplateSpecifierError
from boilerplate.models.template_info import TemplateInfo
from boilerplate.repository.template_repository import TemplateRepository
from boilerplate.types.template_specifier import TemplateSpecifier


class TestTemplateSpecifierBehavior:
    """Tests TemplateSpecifier.from_string parsing behavior for various inputs."""

    @pytest.mark.parametrize(
        "tag,expected_name,expected_version",
        [
            ("project@1.2.3", "project", "1.2.3"),
            ("streamlit@2.0.0rc1", "streamlit", "2.0.0rc1"),
            ("foo-bar_v2@2.5.1", "foo-bar_v2", "2.5.1"),
            (
                "project@2024.7.19",
                "project",
                "2024.7.19",
            ),  # Version normalizes leading zeros
            ("mod@0.0.1.dev1", "mod", "0.0.1.dev1"),
            ("app@1.0.0a1", "app", "1.0.0a1"),  # Alpha release
            ("app@2.0.0b2", "app", "2.0.0b2"),  # Beta release
            ("app@3.0.0rc1", "app", "3.0.0rc1"),  # Release candidate
            ("app@1.0.0.post1", "app", "1.0.0.post1"),  # Post release
            ("app@1.0.0.dev0", "app", "1.0.0.dev0"),  # Development release
        ],
    )
    def test_extracts_name_and_version_from_valid_template_tags(
        self, tag: str, expected_name: str, expected_version: str
    ) -> None:
        """Parses valid template tags into name and semantic version components."""
        result = TemplateSpecifier.from_string(tag)

        assert result is not None, f"Should successfully parse valid tag '{tag}'"
        assert result.name == expected_name
        assert str(result.version) == expected_version

    @pytest.mark.parametrize(
        "invalid_tag,reason",
        [
            ("project@bad", "invalid version format"),
            ("project_1.2.3", "missing @ separator"),
            ("foo", "no version specified"),
            ("@1.2.3", "empty template name"),
            ("v1.2.3", "no @ separator with version"),
            ("project@v", "empty version after @"),
            ("", "completely empty string"),
            ("@", "only @ separator"),
            ("project@@1.2.3", "double @ separator"),
            ("pro ject@1.2.3", "space in template name"),
            ("project@1.2.3@extra", "multiple @ separators"),
        ],
    )
    def test_rejects_malformed_tag_formats(self, invalid_tag: str, reason: str) -> None:  # noqa: ARG002
        """Rejects invalid tag formats and raises InvalidTemplateSpecifierError."""
        with pytest.raises(InvalidTemplateSpecifierError):
            TemplateSpecifier.from_string(invalid_tag)

    @pytest.mark.parametrize(
        "template_name",
        [
            "simple",
            "with-hyphens",
            "with_underscores",
            "MixedCase",
            "numbers123",
            "complex-name_v2",
            "a",  # Single character
            "very-long-template-name-with-many-parts",
        ],
    )
    def test_preserves_valid_template_name_formats(self, template_name: str) -> None:
        """Preserves all valid template name character combinations."""
        tag = f"{template_name}@1.0.0"
        result = TemplateSpecifier.from_string(tag)

        assert result is not None
        assert result.name == template_name
        assert result.version == Version("1.0.0")

    def test_returns_template_specifier_with_proper_types(self) -> None:
        """Returns TemplateSpecifier objects with correct attribute types."""
        result = TemplateSpecifier.from_string("test@1.2.3")

        assert isinstance(result, TemplateSpecifier)
        assert isinstance(result.name, str)
        assert isinstance(result.version, Version)
        assert result.name == "test"
        assert result.version == Version("1.2.3")


class TestTemplateRepositoryInterfaceContract:
    """Tests that TemplateRepository enforces proper interface contract."""

    def test_prevents_direct_instantiation_of_abstract_base(self) -> None:
        """Prevents direct instantiation of abstract TemplateRepository."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            TemplateRepository()  # pyright: ignore[reportAbstractUsage]

    def test_requires_implementation_of_load_templates(self) -> None:
        """Requires concrete classes to implement load_templates."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):

            class IncompleteRepository(TemplateRepository):
                pass

            IncompleteRepository()  # pyright: ignore[reportAbstractUsage]

    def test_allows_instantiation_when_load_templates_implemented(self) -> None:
        """Allows instantiation when load_templates is implemented."""

        class CompleteRepository(TemplateRepository):
            def load_templates(self) -> list[TemplateInfo]:
                return []

        repo = CompleteRepository()
        assert isinstance(repo, TemplateRepository)
        assert repo.load_templates() == []

    def test_interface_exposes_only_load_templates(self, mocker: MockerFixture) -> None:
        """Exposes template loading as the whole repository contract."""
        repo = mocker.Mock(spec=TemplateRepository)
        mock_template = mocker.Mock(spec=TemplateInfo)
        repo.load_templates.return_value = [mock_template]

        templates = repo.load_templates()
        assert templates == [mock_template]

        # Off-contract lookup surface must not exist on the interface
        with pytest.raises(AttributeError):
            _ = repo.list_tags
