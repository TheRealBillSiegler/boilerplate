"""Behavior-driven tests for template composition and generation behavior.

These tests verify the key behaviors users care about when using template
composition, focusing on outcomes rather than implementation details.
"""

import re
import shutil
import sys
from pathlib import Path

import pytest

from boilerplate.catalog import TemplateCatalog
from boilerplate.composition.composer import Composer
from boilerplate.composition.rendering.engine import RenderEngine
from boilerplate.composition.rendering.models.execution_context import ExecutionContext
from boilerplate.composition.resolution import Resolver


class TestTemplateCompositionBehavior:
    """Behavior-driven tests for template composition.

    Given: A template system with base templates and extending templates
    When: Users generate projects using composed templates
    Then: The system should provide merged configurations and execute properly
    """

    def _compose_and_render(
        self,
        template_ref: str,
        catalog: TemplateCatalog,
        execution_context: ExecutionContext,
    ):
        """Compose and render using the three-class pattern."""
        resolver = Resolver()
        composer = Composer()
        render_engine = RenderEngine()

        # Step 1: Resolve dependencies
        resolution = resolver.resolve(template_ref, catalog)

        # Step 2: Merge configurations
        composition = composer.compose(resolution)

        # Step 3: Apply templates
        return render_engine.render(composition, execution_context)

    def _compose_only(self, template_ref: str, catalog: TemplateCatalog):
        """Compose only using the three-class pattern."""
        resolver = Resolver()
        composer = Composer()

        # Step 1: Resolve dependencies
        resolution = resolver.resolve(template_ref, catalog)

        # Step 2: Merge configurations
        return composer.compose(resolution)

    @pytest.fixture(autouse=True)
    def setup_test_environment(self, tmp_path: Path):
        """Set up the test environment and clean up."""
        self.test_output_dir = tmp_path / "behavior_test_project"
        yield
        if self.test_output_dir.exists():
            shutil.rmtree(self.test_output_dir, ignore_errors=True)

    @pytest.mark.slow
    def test_composed_template_merges_dependencies_correctly(
        self, integration_catalog: TemplateCatalog
    ) -> None:
        """Composed templates merge dependencies from all layers."""
        # Build composition using the three-class pattern
        composition = self._compose_only("streamlit", integration_catalog)

        # Create execution context
        execution_context = ExecutionContext(
            destination=self.test_output_dir,
            context_data={
                "project_name": "test_streamlit_app",
            },
            overwrite=True,
            interactive=False,
            skip_tasks=True,
        )

        # Render using RenderEngine
        render_engine = RenderEngine()
        template_info = render_engine.render(composition, execution_context)

        # Verify template composition worked
        assert template_info.name == "streamlit"
        assert self.test_output_dir.exists()

        # Verify the generated pyproject.toml contains merged dependencies
        pyproject_path = self.test_output_dir / "pyproject.toml"
        assert pyproject_path.exists()
        pyproject_content = pyproject_path.read_text(encoding="utf-8")
        assert "streamlit" in pyproject_content
        assert "pydantic" in pyproject_content
        assert (self.test_output_dir / "README.md").exists()
        assert (self.test_output_dir / "src" / "test_streamlit_app").exists()

    @pytest.mark.slow
    def test_base_template_has_empty_dependencies_by_default(
        self, integration_catalog: TemplateCatalog
    ) -> None:
        """Base templates use their own defaults correctly (empty deps)."""
        output_dir = self.test_output_dir / "base_project"

        # Build composition using the three-class pattern
        composition = self._compose_only("project", integration_catalog)

        # Create execution context
        execution_context = ExecutionContext(
            destination=output_dir,
            context_data={
                "project_name": "base_project",
            },
            overwrite=True,
            interactive=False,
            skip_tasks=True,
        )

        # Render using RenderEngine
        render_engine = RenderEngine()
        render_engine.render(composition, execution_context)

        pyproject_path = output_dir / "pyproject.toml"
        assert pyproject_path.exists()
        pyproject_content = pyproject_path.read_text(encoding="utf-8")
        assert "streamlit" not in pyproject_content
        assert "dependencies = [" in pyproject_content
        deps_match = re.search(
            r"dependencies = \[(.*?)\]", pyproject_content, re.DOTALL
        )
        assert deps_match is not None
        deps_content = deps_match.group(1).strip()
        assert not deps_content or deps_content.isspace()

    @pytest.mark.slow
    def test_template_composition_preserves_all_layers(
        self, integration_catalog: TemplateCatalog
    ) -> None:
        """Composed templates include content from all layers."""
        # Build composition using the three-class pattern
        self._compose_only("streamlit", integration_catalog)

        # Create execution context
        execution_context = ExecutionContext(
            destination=self.test_output_dir,
            context_data={
                "project_name": "multi_layer_app",
                "description": "Testing multi-layer composition",
            },
            overwrite=True,
            interactive=False,
            skip_tasks=True,
        )

        # Render using the three-class pattern
        self._compose_and_render("streamlit", integration_catalog, execution_context)

        assert (self.test_output_dir / "README.md").exists()
        assert (self.test_output_dir / "pyproject.toml").exists()
        assert (self.test_output_dir / ".gitignore").exists()
        assert (self.test_output_dir / "src").exists()
        assert (self.test_output_dir / "tests").exists()
        assert (self.test_output_dir / "Dockerfile").exists()

        app_file = self.test_output_dir / "src" / "multi_layer_app" / "app.py"
        assert app_file.exists()
        app_content = app_file.read_text(encoding="utf-8")
        assert "streamlit" in app_content

    @pytest.mark.slow
    def test_user_provided_values_override_composed_defaults(
        self, integration_catalog: TemplateCatalog
    ) -> None:
        """User values override composed template defaults."""
        custom_dependencies = ["fastapi", "uvicorn", "pydantic"]

        # Build composition using the three-class pattern
        composition = self._compose_only("streamlit", integration_catalog)

        # Create execution context
        execution_context = ExecutionContext(
            destination=self.test_output_dir,
            context_data={
                "project_name": "custom_deps_app",
                "dependencies": custom_dependencies,
            },
            overwrite=True,
            interactive=False,
            skip_tasks=True,
        )

        # Render using RenderEngine
        render_engine = RenderEngine()
        render_engine.render(composition, execution_context)

        pyproject_content = (self.test_output_dir / "pyproject.toml").read_text(
            encoding="utf-8"
        )
        assert "fastapi" in pyproject_content
        assert "uvicorn" in pyproject_content
        assert "pydantic" in pyproject_content
        assert "streamlit" not in pyproject_content

    @pytest.mark.slow
    def test_pyproject_requires_python_is_valid_and_uses_system_version(
        self, integration_catalog: TemplateCatalog
    ) -> None:
        """pyproject.toml includes a valid requires-python using system version.

        Ensures ExecutionContext-injected python_version_* fields are present
        and consumed by the template to produce a well-formed constraint.
        """
        output_dir = self.test_output_dir / "requires_python_test"

        # Build composition using the three-class pattern for the base project template
        composition = self._compose_only("project", integration_catalog)

        # Create execution context and render
        execution_context = ExecutionContext(
            destination=output_dir,
            context_data={
                "project_name": "requires_python_project",
            },
            overwrite=True,
            interactive=False,
            skip_tasks=True,
        )

        render_engine = RenderEngine()
        render_engine.render(composition, execution_context)

        # Validate pyproject.toml has a correct requires-python
        pyproject_path = output_dir / "pyproject.toml"
        assert pyproject_path.exists()
        content = pyproject_path.read_text(encoding="utf-8")

        m = re.search(r'requires-python\s*=\s*"([^"]+)"', content)
        assert m is not None, "requires-python field missing in pyproject.toml"
        value = m.group(1)

        # Must be in the form ">= X.Y.Z"
        assert re.fullmatch(r">=\s*\d+\.\d+\.\d+", value) is not None

        expected = f">= {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        assert value == expected, (
            f"requires-python should be '{expected}', got '{value}'"
        )

    @pytest.mark.slow
    def test_post_generation_tasks_execute_in_interactive_mode(
        self, integration_catalog: TemplateCatalog
    ) -> None:
        """Final-layer tasks run even when interactive=True (default CLI mode).

        We assert that the template's post-generation cleanup removed the `_scripts`
        directory, which only happens if tasks executed.
        """
        output_dir = self.test_output_dir / "interactive_task_run"

        # Provide minimal context; interactive=True means the first layer would prompt,
        # but Copier will consume provided answers without blocking if sufficient.

        # Build composition using the three-class pattern
        composition = self._compose_only("streamlit", integration_catalog)

        # Create execution context
        execution_context = ExecutionContext(
            destination=output_dir,
            context_data={
                "project_name": "interactive_task_test",
                "description": "A test project.",
                "dependencies": [],
                "dev_dependencies": [],
                "author_name": "Test User",
                "author_email": "test@example.com",
                "package_index_url": "",
                "container_registry": "ghcr.io",
                "sample_module": False,
            },
            overwrite=True,
            interactive=True,
        )

        # Render using RenderEngine
        render_engine = RenderEngine()
        template_info = render_engine.render(composition, execution_context)

        assert template_info.name == "streamlit"
        # Basic files should exist
        assert (output_dir / "README.md").exists()
        assert (output_dir / "pyproject.toml").exists()

        # Critical assertion: post-generation tasks should have cleaned up `_scripts`
        assert not (output_dir / "_scripts").exists(), (
            "_scripts directory should be removed by post-generation tasks; "
            "this indicates tasks did not run in interactive mode."
        )


class TestTemplateCompositionRegression:
    """Regression tests to prevent composition failures from reoccurring."""

    @pytest.mark.slow
    def test_composed_templates_never_lose_dependencies(
        self, integration_catalog: TemplateCatalog, tmp_path: Path
    ) -> None:
        """Composed templates preserve dependencies from all layers."""
        output_dir = tmp_path / "regression_deps_test"

        # Build composition using the three-class pattern
        resolver = Resolver()
        composer = Composer()
        resolution = resolver.resolve("streamlit", integration_catalog)
        composition = composer.compose(resolution)

        # Create execution context
        execution_context = ExecutionContext(
            destination=output_dir,
            context_data={
                "project_name": "regression_test",
            },
            overwrite=True,
            interactive=False,
            skip_tasks=True,
        )

        # Render using RenderEngine
        render_engine = RenderEngine()
        render_engine.render(composition, execution_context)

        pyproject_content = (output_dir / "pyproject.toml").read_text(encoding="utf-8")
        deps_match = re.search(
            r"dependencies = \[(.*?)\]", pyproject_content, re.DOTALL
        )
        assert deps_match is not None
        deps_content = deps_match.group(1).strip()
        assert deps_content and not deps_content.isspace()
        assert "streamlit" in pyproject_content
        assert "pydantic" in pyproject_content

    @pytest.mark.slow
    def test_template_generation_always_completes_successfully(
        self, integration_catalog: TemplateCatalog, tmp_path: Path
    ) -> None:
        """Template generation completes without errors."""
        output_dir = tmp_path / "regression_completion_test"

        # Build composition using the three-class pattern
        resolver = Resolver()
        composer = Composer()
        resolution = resolver.resolve("streamlit", integration_catalog)
        composition = composer.compose(resolution)

        # Create execution context
        execution_context = ExecutionContext(
            destination=output_dir,
            context_data={
                "project_name": "completion_test",
            },
            overwrite=True,
            interactive=False,
            skip_tasks=True,
        )

        # Render using RenderEngine
        render_engine = RenderEngine()
        template_info = render_engine.render(composition, execution_context)

        assert template_info.name == "streamlit"
        assert output_dir.exists()
        assert (output_dir / "pyproject.toml").exists()
