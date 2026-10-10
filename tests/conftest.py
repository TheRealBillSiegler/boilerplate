import io
import json
import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from packaging.version import Version
from pytest_mock import MockerFixture
from rich.console import Console
from typer.testing import CliRunner

from boilerplate.catalog import TemplateCatalog
from boilerplate.cli.display.core import Display
from boilerplate.cli.seams import Seams
from boilerplate.cli.utils import build_template_catalog
from boilerplate.composition.composer import Composer
from boilerplate.composition.merging import CopierConfigMerger
from boilerplate.composition.models import Composition
from boilerplate.composition.rendering.engine import final_template_info
from boilerplate.composition.rendering.models.execution_context import ExecutionContext
from boilerplate.composition.resolution import Resolution
from boilerplate.integrations.copier_types import Template as CopierTemplate
from boilerplate.models.template_info import TemplateInfo
from boilerplate.models.template_meta import TemplateMeta
from boilerplate.repository.directory_repository import DirectoryTemplateRepository
from boilerplate.settings import Settings


@pytest.fixture()
def subprocess_cli_runner() -> Callable[..., subprocess.CompletedProcess[str]]:
    """Canonical subprocess-based CLI runner for end-to-end CLI integration tests.

    Executes the CLI via a real subprocess with robust UTF-8 handling; this avoids
    UnicodeDecodeError warnings and ensures deterministic output capture across
    platforms.
    """

    def run_cli_command(
        *args: str, timeout: int = 90
    ) -> subprocess.CompletedProcess[str]:
        # Ensure UTF-8 for child process I/O
        env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
        return subprocess.run(
            [sys.executable, "-m", "boilerplate", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            env=env,
        )

    return run_cli_command


# Module-level helper functions
def create_copier_template(location: Path) -> CopierTemplate:
    """Create a test CopierTemplate with basic structure."""
    return CopierTemplate(str(location))


class RecordingRenderer:
    """Fakes `Renderer` by recording calls instead of driving Copier.

    Satisfies the `Renderer` Protocol structurally (see
    `boilerplate.composition.rendering.renderer`); passed to `new` through
    `Seams` so tests can assert on what the command sent to the renderer
    instead of patching the command's engine import.

    Attributes:
        calls: Every `(composition, ctx)` pair `render` was called with, in
            call order.
        error: Exception `render` raises instead of returning, when set.
    """

    def __init__(self, error: Exception | None = None) -> None:
        """Initialize the recorder with an optional render-time failure.

        Args:
            error: When set, `render` raises this instead of succeeding.
        """
        self.calls: list[tuple[Composition, ExecutionContext]] = []
        self.error = error

    def render(self, composition: Composition, ctx: ExecutionContext) -> TemplateInfo:
        """Record the call and return the root layer's `TemplateInfo`.

        Args:
            composition: Composition the caller wants rendered.
            ctx: Execution parameters for the (unperformed) render.

        Returns:
            The `TemplateInfo` `RenderEngine.render` would return for this
            composition's final layer.

        Raises:
            Exception: `self.error`, when set at construction.
        """
        self.calls.append((composition, ctx))
        if self.error is not None:
            raise self.error
        final_layer = composition.layers[-1]
        return final_template_info(
            final_path=final_layer.path, fallback_name=final_layer.name
        )


@pytest.fixture()
def renderer() -> RecordingRenderer:
    """Provide a `RecordingRenderer` standing in for `RenderEngine` at the CLI seam."""
    return RecordingRenderer()


@pytest.fixture()
def seams(renderer: RecordingRenderer) -> Seams:
    """`Seams` wired to the `renderer` fixture, ready to pass as `obj` to the runner."""
    return Seams(renderer=renderer)


@pytest.fixture()
def typer_cli_runner() -> CliRunner:
    """Function-scoped Typer CLI runner to avoid stream issues in parallel tests."""
    return CliRunner()


@pytest.fixture()
def interactive_tty(mocker: MockerFixture) -> None:
    """Pretends stdin is a real TTY so `new` may take the interactive path.

    Click's CliRunner installs a non-TTY stdin for every invocation (and
    pytest's capture usually does too), so without this the non-TTY guard
    in `boilerplate new` fails closed before RenderEngine is reached.
    """
    mocker.patch(
        "boilerplate.cli.commands.new._stdin_supports_prompts", return_value=True
    )


@pytest.fixture(scope="session")
def real_templates_dir() -> Path:
    """Get the path to the real templates directory (session-scoped)."""
    return Path(__file__).parent.parent / "src" / "boilerplate" / "templates"


@pytest.fixture(scope="session")
def integration_catalog(real_templates_dir: Path) -> TemplateCatalog:
    """Shared TemplateCatalog for integration tests with real templates loaded.

    This enables app-layer tests (orchestrator) without depending on TemplateEngine.
    """
    repository = DirectoryTemplateRepository(real_templates_dir)
    registry = TemplateCatalog()
    registry.register_many(repository.load_templates())
    return registry


# Common, lightweight shared fixtures
@pytest.fixture()
def temp_project_dir(tmp_path: Path) -> Path:
    """Provide an empty directory to use as --output for `boilerplate new` tests."""
    return tmp_path / "project"


@pytest.fixture()
def fake_template_dir(tmp_path: Path) -> Path:
    """Create a throw-away template directory named ``mytpl``.

    Includes the minimal files required for TemplateRegistry to treat it as a
    valid template.
    """
    tpl = tmp_path / "mytpl"
    tpl.mkdir(parents=True)
    (tpl / "copier.yml").write_text("# empty config\n")
    (tpl / "boilerplate.yml").write_text(
        """
schema_version: "1.0.0"
name: "mytpl"
description: "A test template."
version: "1.0.0"
extends: []
"""
    )
    return tmp_path


def _present_banner_host(
    mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Present a 120 by 40 host that could draw the banner, stdout aside.

    Whether a screen reader runs depends on the host, so that probe is
    replaced; the size and ``TERM`` come from the environment, where Rich and
    the probe read them.
    """
    mocker.patch(
        "boilerplate.cli.display.terminal_probe._screen_reader_running",
        return_value=False,
    )
    monkeypatch.setenv("COLUMNS", "120")
    monkeypatch.setenv("LINES", "40")
    monkeypatch.setenv("TERM", "xterm-256color")
    for name in ("NO_COLOR", "FORCE_COLOR", "TTY_COMPATIBLE"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture()
def banner_host(mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    """Present a host that could draw the banner, leaving stdout as it is."""
    _present_banner_host(mocker, monkeypatch)


@pytest.fixture()
def banner_terminal(mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    """Present stdout as a 120 by 40 terminal that can draw the banner.

    CliRunner's stdout is never a terminal, so the probe is told it is one.
    """
    _present_banner_host(mocker, monkeypatch)
    mocker.patch(
        "boilerplate.cli.display.terminal_probe._is_terminal", return_value=True
    )


@pytest.fixture(autouse=True)
def clear_boilerplate_env(monkeypatch: pytest.MonkeyPatch):
    """Remove all BOILERPLATE_* env vars and the generic CI var for hermetic isolation.

    CI is scrubbed too so that a real CI runner's ambient `CI=true` can never
    leak into a test asserting on boilerplate's own env vars.
    """
    for k in list(os.environ):
        if k.startswith("BOILERPLATE_"):
            monkeypatch.delenv(k, raising=False)
    monkeypatch.delenv("CI", raising=False)
    yield


# Core template creation utilities


@dataclass
class TemplateConfig:
    """Configuration for template creation to reduce parameter count."""

    name: str = ""
    version: str = "1.0.0"
    description: str = "Test template"
    extends: list[str] | None = None
    location: Path | None = None
    mock: bool = False


@pytest.fixture()
def catalog_builder() -> Callable[..., TemplateCatalog]:
    """Provide a factory to build a TemplateCatalog from Settings or explicit dirs.

    Usage:
      - catalog_builder(settings=my_settings)
      - catalog_builder(default_dir=path1, extra_dirs=[path2, path3])
    """

    def make(
        *,
        settings: Settings | None = None,
        default_dir: Path,
        extra_dirs: list[Path] | None = None,
    ) -> TemplateCatalog:
        """Create a TemplateCatalog.

        Args:
            settings: Optional pre-built Settings object. When provided, default_dir and
                extra_dirs are ignored.
            default_dir: Default templates directory when constructing Settings here.
            extra_dirs: Additional template directories.

        Returns:
            A TemplateCatalog built from the specified configuration.
        """
        cfg = settings or Settings(
            default_templates_dir=default_dir,
            extra_template_dirs=extra_dirs or [],
        )
        return build_template_catalog(None, cfg)

    return make


@pytest.fixture
def template_factory(tmp_path: Path, mocker: MockerFixture):
    """Provide a factory for creating real and mock TemplateInfo instances."""

    def _create_template_info(
        name: str,
        version: str = "1.0.0",
        **kwargs,
    ) -> TemplateInfo:
        """Create templates with custom parameters - supports both old and new API.

        Args:
            name: Template name
            version: Template version
            **kwargs: Additional configuration (description, extends, location, mock)
        """
        # Extract keyword arguments and create TemplateConfig
        config = TemplateConfig(
            name=name,
            version=version,
            description=kwargs.get("description", f"Test template {name}"),
            extends=kwargs.get("extends", []),
            location=kwargs.get("location"),
            mock=kwargs.get("mock", False),
        )

        if config.mock:
            # Create mock TemplateInfo (consolidated from make_template_factory)
            meta_mock = mocker.Mock()
            meta_mock.version = config.version
            meta_mock.extends = config.extends

            template = mocker.Mock(spec=TemplateInfo)
            template.name = config.name
            template.meta = meta_mock

            # Mock the specifier property consistently
            specifier_mock = mocker.Mock()
            specifier_mock.__str__ = mocker.Mock(
                return_value=f"{config.name}@{config.version}"
            )
            template.specifier = specifier_mock

            return template

        # Create real TemplateInfo (consolidated from create_template_info)
        # Add worker ID to template location for parallel execution isolation
        worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
        unique_name = f"{config.name}_{worker_id}_{id(tmp_path)}"
        template_location = config.location or tmp_path / unique_name

        # Provide a simple default questionnaire
        questions_data = {
            "project_name": {"type": "str", "help": "Project name"},
            "description": {"type": "str", "default": "A test project"},
        }

        meta = TemplateMeta(
            name=config.name,
            version=Version(config.version),
            description=config.description,
            extends=config.extends or [],
        )

        # Create template directory and persist questionnaire so Copier can source it
        template_location.mkdir(parents=True, exist_ok=True)
        copier_file = template_location / "copier.yml"
        if not copier_file.exists():
            copier_file.write_text(json.dumps(questions_data), encoding="utf-8")

        copier_template = create_copier_template(template_location)
        # Expose questions directly for tests
        copier_template.questions_data = questions_data

        return TemplateInfo(
            name=config.name,
            meta=meta,
            location=template_location,
            copier_template=copier_template,
        )

    return _create_template_info


@pytest.fixture
def resolution_factory(template_factory: Callable[..., TemplateInfo], tmp_path: Path):
    """Provide a factory to build a Resolution from a mapping of specifiers to configs.

    The configs are not applied automatically; tests that need per-layer compiled
    schemas should monkeypatch planner.compile_layer_schemas to return a list
    of dicts corresponding to the provided specifier order.

    Args:
        template_factory: Fixture to create TemplateInfo objects
        tmp_path: Temporary directory to place template locations

    Returns:
        Callable taking (spec_to_config: dict[str, dict],
        deps: dict[str, list[str]] | None) and returning a Resolution with
        TemplateInfo objects.
    """

    def _make(
        spec_to_config: dict[str, dict[str, Any]],
        deps: dict[str, list[str]] | None = None,
    ) -> Resolution:
        templates: dict[str, TemplateInfo] = {}
        # Add worker ID for parallel execution isolation
        worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
        for spec in spec_to_config:
            if "@" in spec:
                name, version = spec.split("@", 1)
            else:
                name, version = spec, "1.0.0"
            # Create unique template location for each worker
            unique_template_path = tmp_path / f"{name}_{worker_id}_{id(tmp_path)}"
            ti = template_factory(name, version, location=unique_template_path)
            templates[spec] = ti
        if deps is None:
            deps = {s: [] for s in spec_to_config}
        return Resolution(deps=deps, templates=templates)

    return _make


@pytest.fixture()
def composition_factory(resolution_factory: Callable[..., Resolution]):
    """Provide a Composition factory for testing rendering/merging."""

    def _create_composition(
        template_specs: list[str],
        layer_schemas: list[dict[str, Any]] | None = None,
        final_schema: dict[str, Any] | None = None,
    ) -> Composition:
        """Create a composition with the specified templates and schemas.

        Args:
            template_specs: List of specifiers, e.g., 'base@1.0.0', 'child@1.0.0'
            layer_schemas: Per-layer configuration (defaults to empty dicts)
            final_schema: Final merged schema (defaults to empty dict)
        """
        # Default schemas if not provided
        if layer_schemas is None:
            layer_schemas = [{} for _ in template_specs]
        if final_schema is None:
            final_schema = {}

        # Create resolution from specs
        spec_to_config = {spec: {} for spec in template_specs}
        resolution = resolution_factory(spec_to_config)

        # Create a custom extract_config function that returns the layer schemas
        # Use a local copy to avoid closure capture issues in parallel execution
        layer_schema_map = {}
        for i, spec in enumerate(template_specs):
            config = layer_schemas[i] if i < len(layer_schemas) else {}
            layer_schema_map[spec] = config.copy()  # Defensive copy

        def extract_config_for_test(template_info: TemplateInfo) -> dict[str, Any]:
            """Extract config from layer_schemas instead of template directory."""
            spec = f"{template_info.name}@{template_info.meta.version}"
            return layer_schema_map.get(spec, {})

        composition = Composer(extract_config=extract_config_for_test).compose(
            resolution,
            include_states=False,
            include_deltas=False,
        )

        # Merge final_schema into the composition's final result
        if final_schema:
            merger = CopierConfigMerger()
            configs_to_merge: list[dict[str, object]] = [
                dict(composition.final),
                dict(final_schema),
            ]
            merged_final = merger.merge(configs_to_merge)
            # Update the composition's final schema
            composition = composition.model_copy(update={"final": merged_final})

        return composition

    return _create_composition


# Core template test data - single source of truth
STANDARD_TEST_TEMPLATES = [
    ("project", "1.2.3", "Project template"),
    ("streamlit", "2.0.0rc1", "Streamlit template"),
    ("module", "0.2.0", "Module template"),
]


@pytest.fixture()
def standard_templates_for_directory_tests():
    """Provide standard template data for directory repository tests."""
    return STANDARD_TEST_TEMPLATES[:2]  # Just project and streamlit


@pytest.fixture
def templates_dir_factory(tmp_path: Path):
    """Provide a factory to create on-disk template directories for repository tests.

    This consolidates repeated inline file system setup across tests. It creates
    one subdirectory per template entry, writes a minimal boilerplate.yml with
    name/version, and writes a copier.yml with the provided questions schema.

    Usage:
      root = templates_dir_factory([
          ("project", "1.2.3", {"questions": {"foo": {"type": "str"}}}),
          ("streamlit", "2.0.0rc1", {"questions": {"bar": {"type": "int"}}}),
      ])

      # For multiple versions of the same template name, pass multiple tuples
      # with the same name but different versions. The directories will be
      # suffixed (e.g., name_v1, name_v2) but boilerplate.yml will keep the
      # canonical template name so the repository groups them correctly.

    Args:
        tmp_path: Base temporary directory provided by pytest for file creation.
        entries: list of tuples (name, version, copier_yaml_dict)

    Returns:
        Path to the root directory containing all created template subdirs.
    """

    def version_to_suffix(ver: str) -> str:
        # Generate a filesystem-friendly suffix for a version string
        return (
            ver.replace("+", "plus")
            .replace("-", "-")
            .replace(".", "_")
            .replace(" ", "_")
        )

    def create(entries: list[tuple[str, str, dict[str, Any]]]) -> Path:
        root = tmp_path / "templates_root"
        root.mkdir(parents=True, exist_ok=True)
        # Track counts per name to avoid collisions when versions map to same suffix
        per_name_counts: dict[str, int] = {}
        for name, version, copier_dict in entries:
            count = per_name_counts.get(name, 0)
            per_name_counts[name] = count + 1
            suffix = version_to_suffix(version)
            # For multiple versions of the same name, create distinct dirs
            dir_name = f"{name}_{suffix}" if count > 0 or suffix else name
            tpl_dir = root / dir_name
            tpl_dir.mkdir(parents=True, exist_ok=True)

            # Minimal boilerplate.yml
            (tpl_dir / "boilerplate.yml").write_text(
                f"name: {name}\nversion: {version}\n",
                encoding="utf-8",
            )

            # Copier questions
            copier_payload = (
                copier_dict
                if "questions" in copier_dict
                else {"questions": copier_dict}
            )
            (tpl_dir / "copier.yml").write_text(
                json.dumps(copier_payload), encoding="utf-8"
            )

        return root

    return create


@pytest.fixture()
def captured_display() -> tuple[Display, io.StringIO]:
    """Provide a Display wired to a StringIO buffer for easy output capture.

    The Console is constructed with deterministic settings so that snapshot
    output is identical on Windows and Linux (no legacy_windows substitution,
    no ANSI codes, fixed width).

    Returns a tuple of (display, buffer). Tests can write to the display and
    then call buffer.getvalue() to assert on the rendered output.
    """
    display = Display()
    buffer = io.StringIO()
    deterministic_console = Console(
        theme=display.theme,
        file=buffer,
        width=80,
        color_system=None,
        legacy_windows=False,
    )
    display.console = deterministic_console
    display.error_console = deterministic_console
    return display, buffer


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Group all snapshot-using tests onto one xdist worker.

    We co-locate tests that either:
        - are marked with @pytest.mark.snapshot, or
        - request the 'snapshot' fixture (from syrupy)

    This prevents concurrent writes to the same snapshot files when running in
    parallel (e.g., with --snapshot-update), while allowing non-snapshot tests to
    run freely across workers.

    Also auto-applies the 'integration' marker to tests under tests/integration/.
    """
    integration_dir = Path(__file__).parent / "integration"
    for item in items:
        # True if explicitly marked as a snapshot test
        has_snapshot_mark = any(mark.name == "snapshot" for mark in item.iter_markers())
        # True if the test function uses the syrupy 'snapshot' fixture
        uses_snapshot_fixture = "snapshot" in getattr(item, "fixturenames", [])

        if has_snapshot_mark or uses_snapshot_fixture:
            # Ensure all snapshot tests run on the same worker
            item.add_marker(pytest.mark.xdist_group(name="snapshot_tests"))

        if item.path.is_relative_to(integration_dir):
            item.add_marker(pytest.mark.integration)
