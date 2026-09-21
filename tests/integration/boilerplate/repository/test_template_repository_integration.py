"""Integration tests for TemplateRepository implementations with real templates.

These tests verify end-to-end behavior of repository implementations using actual
template files and directory structures, focusing on real-world usage scenarios.
"""

from pathlib import Path

import pytest

from boilerplate.repository.directory_repository import DirectoryTemplateRepository


@pytest.fixture
def repo_with_real_templates(real_templates_dir: Path) -> DirectoryTemplateRepository:
    """Create a DirectoryTemplateRepository using real template files."""
    return DirectoryTemplateRepository(real_templates_dir)


class TestUserCanDiscoverTemplates:
    """Tests user workflows for discovering available templates."""

    def test_user_can_discover_all_available_templates(
        self, repo_with_real_templates: DirectoryTemplateRepository
    ) -> None:
        """User can see all templates available for project creation."""
        templates = repo_with_real_templates.load_templates()

        # User should find templates to work with
        assert len(templates) > 0, (
            "User should see available templates for project creation"
        )

        # Each template should provide clear identification
        for template in templates:
            assert len(template.name) > 0, (
                "Template should have a clear name for user selection"
            )
            assert template.meta.version is not None, (
                "Template should show version for user confidence"
            )
            assert template.location is not None
            assert template.location.exists(), (
                "Template files should be available for use"
            )

    def test_each_template_name_is_loaded_once(
        self, repo_with_real_templates: DirectoryTemplateRepository
    ) -> None:
        """Users see a single, unambiguous entry per template name."""
        templates = repo_with_real_templates.load_templates()
        names = [template.name for template in templates]

        assert len(names) == len(set(names)), (
            "Duplicate template names would confuse users choosing a template"
        )

    def test_repeated_loading_provides_consistent_experience(
        self, repo_with_real_templates: DirectoryTemplateRepository
    ) -> None:
        """Users get consistent results when loading templates multiple times."""
        first = {tpl.name: tpl for tpl in repo_with_real_templates.load_templates()}

        for _ in range(2):
            again = {tpl.name: tpl for tpl in repo_with_real_templates.load_templates()}
            assert again.keys() == first.keys()
            for name, template in again.items():
                assert template.meta.version == first[name].meta.version
                assert template.location == first[name].location


class TestTemplatesAreReadyForProjectCreation:
    """Tests that templates provide everything needed for project generation."""

    def test_templates_provide_all_required_project_files(
        self, repo_with_real_templates: DirectoryTemplateRepository
    ) -> None:
        """Templates include all files needed for project creation."""
        templates = repo_with_real_templates.load_templates()

        for template in templates:
            assert template.location is not None

            location = template.location

            # Templates should include configuration for project generation
            boilerplate_yml = location / "boilerplate.yml"
            copier_yml = location / "copier.yml"

            assert boilerplate_yml.exists(), (
                f"Template {template.name} should provide boilerplate configuration for project setup"
            )
            assert copier_yml.exists(), (
                f"Template {template.name} should provide copier configuration for project generation"
            )

            # Configuration files should contain actual settings
            assert boilerplate_yml.stat().st_size > 0, (
                f"Template {template.name} should have meaningful boilerplate configuration"
            )
            assert copier_yml.stat().st_size > 0, (
                f"Template {template.name} should have meaningful copier configuration"
            )

    def test_templates_provide_meaningful_project_information(
        self, repo_with_real_templates: DirectoryTemplateRepository
    ) -> None:
        """Templates provide clear information to help users choose the right one."""
        templates = repo_with_real_templates.load_templates()

        for template in templates:
            # Users should understand what the template creates
            meta = template.meta
            assert meta.name == template.name
            assert len(meta.description) > 0, (
                f"Template {template.name} should explain what kind of project it creates"
            )

            # Template dependencies should be clearly specified
            assert isinstance(meta.extends, list), (
                f"Template {template.name} should clearly specify any dependencies"
            )

    def test_templates_are_ready_for_immediate_use(
        self, repo_with_real_templates: DirectoryTemplateRepository
    ) -> None:
        """Templates are fully prepared for generation without additional setup."""
        templates = repo_with_real_templates.load_templates()

        for template in templates:
            copier_template = template.copier_template
            assert copier_template is not None, (
                f"Template {template.name} should be ready for project generation"
            )

            # Template should be properly configured for copier
            assert hasattr(copier_template, "local_abspath")
            assert hasattr(copier_template, "metadata")
            assert hasattr(copier_template, "config_data")

            # Template files should be accessible for project creation
            src_path = Path(copier_template.local_abspath)
            assert src_path.exists(), (
                f"Template {template.name} files should be available for copying"
            )
            assert src_path.is_dir(), (
                f"Template {template.name} should be organized as a complete project structure"
            )

    def test_template_dependencies_can_be_resolved_for_complete_projects(
        self, repo_with_real_templates: DirectoryTemplateRepository
    ) -> None:
        """Template dependencies are available when templates extend others."""
        templates = repo_with_real_templates.load_templates()
        available_names = {template.name for template in templates}

        for template in templates:
            # Any template dependencies should be available
            for parent_name in template.meta.extends:
                assert parent_name in available_names, (
                    f"Template {template.name} requires {parent_name} for complete project creation, "
                    f"but {parent_name} is not available"
                )
