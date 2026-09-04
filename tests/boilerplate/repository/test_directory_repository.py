"""Tests DirectoryTemplateRepository template discovery and loading.

This module tests the DirectoryTemplateRepository's ability to discover, validate,
and load templates stored in a directory structure. Tests are organized by
functional area and focus on behavior rather than implementation details.
"""

import logging
from collections.abc import Callable
from pathlib import Path

import pytest
from packaging.version import Version
from pytest_mock import MockerFixture

from boilerplate.common.exceptions import MetadataValidationError
from boilerplate.integrations.copier_types import Template as CopierTemplate
from boilerplate.models.template_meta import TemplateMeta
from boilerplate.repository.directory_repository import DirectoryTemplateRepository


class TestDirectoryTemplateRepositoryBasicOperations:
    """Tests core repository operations for template discovery and loading."""

    @pytest.fixture
    def templates_with_standard_layout(
        self,
        templates_dir_factory: "Callable[[list[tuple[str, str, dict[str, object]]]], Path]",
        standard_templates_for_directory_tests: list[tuple[str, str, str]],
    ) -> Path:
        """Creates a standard template directory layout for testing basic operations."""
        return templates_dir_factory(
            [
                (name, version, {"questions": {"foo": {"type": "str"}}})
                for name, version, _ in standard_templates_for_directory_tests
            ]
        )

    def test_discovers_all_available_templates(
        self, templates_with_standard_layout: Path
    ) -> None:
        """Repository discovers and loads all valid templates."""
        repo = DirectoryTemplateRepository(templates_with_standard_layout)

        loaded_tags = {
            f"{tpl.name}@{tpl.meta.version}" for tpl in repo.load_templates()
        }
        expected_tags = {"project@1.2.3", "streamlit@2.0.0rc1"}

        assert loaded_tags == expected_tags

    def test_loaded_templates_are_ready_for_use(
        self, templates_with_standard_layout: Path
    ) -> None:
        """Loaded templates carry metadata and a copier template."""
        repo = DirectoryTemplateRepository(templates_with_standard_layout)

        templates = {tpl.name: tpl for tpl in repo.load_templates()}
        project = templates["project"]

        assert project.meta.version == Version("1.2.3")
        assert isinstance(project.copier_template, CopierTemplate)
        assert project.location is not None


class TestDirectoryTemplateRepositoryVersionHandling:
    """Tests repository behavior with multiple versions of the same template."""

    @pytest.fixture
    def templates_with_multiple_versions(
        self,
        templates_dir_factory: "Callable[[list[tuple[str, str, dict[str, object]]]], Path]",
    ) -> Path:
        """Creates templates directory with multiple versions of the same template."""
        return templates_dir_factory(
            [
                ("mytpl", "1.1.0", {"questions": {"alpha": {"type": "str"}}}),
                ("mytpl", "1.2.0", {"questions": {"beta": {"type": "int"}}}),
            ]
        )

    def test_loads_only_highest_version_when_multiple_exist(
        self, templates_with_multiple_versions: Path
    ) -> None:
        """Repository keeps only the highest version when multiple versions exist."""
        repo = DirectoryTemplateRepository(templates_with_multiple_versions)
        templates = repo.load_templates()

        assert len(templates) == 1
        template = templates[0]
        assert template.name == "mytpl"
        assert template.meta.version == Version("1.2.0")
        assert isinstance(template.copier_template, CopierTemplate)


class TestDirectoryTemplateRepositoryErrorHandling:
    """Tests repository behavior with invalid configurations and edge cases."""

    def test_handles_empty_directory_gracefully(self, tmp_path: Path) -> None:
        """Repository handles empty directories without errors."""
        repo = DirectoryTemplateRepository(tmp_path)

        assert repo.load_templates() == []

    def test_skips_directories_missing_required_files(self, tmp_path: Path) -> None:
        """Repository skips directories that don't have required configuration files."""
        # Create valid template
        valid_dir = tmp_path / "valid_template"
        valid_dir.mkdir()
        (valid_dir / "boilerplate.yml").write_text("name: valid\nversion: 1.0.0\n")
        (valid_dir / "copier.yml").write_text("questions:\n  foo:\n    type: str\n")

        # Create directories with missing files
        missing_boilerplate = tmp_path / "missing_boilerplate"
        missing_boilerplate.mkdir()
        (missing_boilerplate / "copier.yml").write_text(
            "questions:\n  bar:\n    type: str\n"
        )

        missing_copier = tmp_path / "missing_copier"
        missing_copier.mkdir()
        (missing_copier / "boilerplate.yml").write_text(
            "name: missing_copier\nversion: 1.0.0\n"
        )

        missing_both = tmp_path / "missing_both"
        missing_both.mkdir()

        # Create a regular file (should be ignored)
        (tmp_path / "regular_file.txt").write_text("not a directory")

        repo = DirectoryTemplateRepository(tmp_path)
        templates = repo.load_templates()

        assert len(templates) == 1
        assert templates[0].name == "valid"
        assert templates[0].meta.version == Version("1.0.0")

    @pytest.mark.parametrize(
        "metadata_content,should_load",
        [
            ("name: foo\nversion: 1.0.0\n", True),  # Valid metadata
            ("name: bar\nversion: 1.0.1\n", True),  # Valid metadata
            ("name: baz\nversion: not-a-version\n", False),  # Invalid version
            ("", False),  # Empty file
            ("name: missing_version\n", False),  # Missing version
            ("version: 1.0.0\n", False),  # Missing name
        ],
    )
    def test_validates_template_metadata(
        self, tmp_path: Path, metadata_content: str, should_load: bool
    ) -> None:
        """Repository validates template metadata, skipping malformed candidates.

        Per docs/design/03-template-system.md §Discovery Algorithm, invalid
        candidates are skipped with a warning rather than aborting discovery
        of the whole catalog.
        """
        template_dir = tmp_path / "test_template"
        template_dir.mkdir()
        (template_dir / "boilerplate.yml").write_text(metadata_content)
        (template_dir / "copier.yml").write_text("questions:\n  test:\n    type: str\n")

        repo = DirectoryTemplateRepository(tmp_path)
        assert len(repo.load_templates()) == (1 if should_load else 0)

    def test_handles_directory_name_different_from_metadata_name(
        self, tmp_path: Path
    ) -> None:
        """Uses metadata name for template identification, not directory name."""
        # Directory name differs from metadata name
        template_dir = tmp_path / "directory_name"
        template_dir.mkdir()
        (template_dir / "boilerplate.yml").write_text(
            "name: metadata_name\nversion: 1.2.3\n"
        )
        (template_dir / "copier.yml").write_text("questions:\n  test:\n    type: str\n")

        repo = DirectoryTemplateRepository(tmp_path)
        names = {tpl.name for tpl in repo.load_templates()}

        # Should use metadata name, not directory name
        assert names == {"metadata_name"}


class TestDirectoryTemplateRepositoryMalformedCandidateIsolation:
    """A malformed candidate does not break discovery of the rest of the catalog.

    Per docs/design/03-template-system.md §Discovery Algorithm, invalid
    candidates are skipped with a warning that names the offending file,
    rather than aborting the whole catalog load.
    """

    def test_one_malformed_directory_does_not_block_other_templates(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A malformed template directory is skipped; sibling templates still load."""
        valid_dir = tmp_path / "valid_template"
        valid_dir.mkdir()
        (valid_dir / "boilerplate.yml").write_text("name: valid\nversion: 1.0.0\n")
        (valid_dir / "copier.yml").write_text("questions:\n  foo:\n    type: str\n")

        malformed_dir = tmp_path / "malformed_template"
        malformed_dir.mkdir()
        malformed_boilerplate_yml = malformed_dir / "boilerplate.yml"
        malformed_boilerplate_yml.write_text("name: missing_version\n")
        (malformed_dir / "copier.yml").write_text("questions:\n  bar:\n    type: str\n")

        with caplog.at_level(logging.WARNING):
            repo = DirectoryTemplateRepository(tmp_path)

        templates = repo.load_templates()
        assert {tpl.name for tpl in templates} == {"valid"}

        warnings = [record.getMessage() for record in caplog.records]
        expected_code = MetadataValidationError().error_code
        assert expected_code is not None
        assert any(
            str(malformed_boilerplate_yml) in message and expected_code in message
            for message in warnings
        )

    def test_metadata_load_race_is_skipped_with_warning_naming_the_file(
        self, tmp_path: Path, mocker: MockerFixture, caplog: pytest.LogCaptureFixture
    ) -> None:
        """FileNotFoundError during load (TOCTOU race) is skipped with warning."""
        valid_dir = tmp_path / "valid_template"
        valid_dir.mkdir()
        (valid_dir / "boilerplate.yml").write_text("name: valid\nversion: 1.0.0\n")
        (valid_dir / "copier.yml").write_text("questions:\n  foo:\n    type: str\n")

        raced_dir = tmp_path / "raced_template"
        raced_dir.mkdir()
        raced_boilerplate_yml = raced_dir / "boilerplate.yml"
        raced_boilerplate_yml.write_text("name: raced\nversion: 1.0.0\n")
        (raced_dir / "copier.yml").write_text("questions:\n  bar:\n    type: str\n")

        original_load = TemplateMeta.load

        def flaky_load(path: Path) -> TemplateMeta:
            if path == raced_dir:
                raise FileNotFoundError(raced_boilerplate_yml)
            return original_load(path)

        mocker.patch(
            "boilerplate.repository.directory_repository.TemplateMeta.load",
            side_effect=flaky_load,
        )

        with caplog.at_level(logging.WARNING):
            repo = DirectoryTemplateRepository(tmp_path)

        templates = repo.load_templates()
        assert {tpl.name for tpl in templates} == {"valid"}

        warnings = [record.getMessage() for record in caplog.records]
        assert any(str(raced_boilerplate_yml) in message for message in warnings)
