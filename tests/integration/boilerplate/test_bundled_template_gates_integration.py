"""Every bundled template renders output that passes its own lint/type/test gates.

Renders each template under ``src/boilerplate/templates`` with default answers
(no post-generation tasks) and runs the same commands the quickstart tells a
new user to run.

Two layers, deliberately different toolchains:

- `test_ruff_format_check`/`test_ruff_check` run against *this repo's*
  dev/CI-pinned ruff (`sys.executable -m ruff`, frozen via `uv.lock`). Fast,
  no install step, and the first line of defense against template edits that
  reintroduce drift.
- `test_under_own_resolved_toolchain` additionally re-runs ruff against the
  *rendered project's own* `uv sync`-resolved ruff (unpinned in the bundled
  `pyproject.toml.jinja`, so it floats to whatever's current on PyPI at a
  real user's sync time), alongside pyright and pytest. That's the actual
  toolchain a new user hits, and the version skew between it and this
  repo's pinned ruff is what produced the drift this suite guards against.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from boilerplate.catalog import TemplateCatalog
from boilerplate.composition import Composer, Resolver
from boilerplate.composition.rendering.engine import RenderEngine
from boilerplate.composition.rendering.models.execution_context import ExecutionContext

_TEMPLATES_DIR = Path(__file__).parents[3] / "src" / "boilerplate" / "templates"
_TEMPLATE_NAMES = sorted(
    p.parent.name for p in _TEMPLATES_DIR.glob("*/boilerplate.yml")
)


def _render(name: str, catalog: TemplateCatalog, destination: Path) -> None:
    """Renders `name` from `catalog` into `destination` with defaults, no tasks."""
    resolution = Resolver().resolve(name, catalog)
    composition = Composer().compose(resolution)
    ctx = ExecutionContext(
        destination=destination,
        overwrite=True,
        interactive=False,
        skip_tasks=True,  # post-gen tasks (uv sync/git init) are out of scope here
    )
    RenderEngine().render(composition, ctx)


def _run(cmd: list[str], *, cwd: Path, label: str) -> None:
    """Runs `cmd` in `cwd`; fails the test with captured output if it errors."""
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
    assert result.returncode == 0, f"{label}:\n{result.stdout}{result.stderr}"


@pytest.fixture(params=_TEMPLATE_NAMES)
def template_name(request: pytest.FixtureRequest) -> str:
    """Parametrizes dependent fixtures/tests over every bundled template."""
    return request.param


@pytest.fixture()
def rendered_template(
    template_name: str, integration_catalog: TemplateCatalog, tmp_path: Path
) -> Path:
    """Renders `template_name` with default answers into an isolated tmp dir.

    The destination is deliberately NOT named after the template: the
    project's package name defaults to its folder name, and a folder named
    e.g. "streamlit" would shadow the real `streamlit` dependency (own
    package resolves before site-packages), which is a test-harness
    collision, not a template defect.
    """
    destination = tmp_path / "generated"
    _render(template_name, integration_catalog, destination)
    return destination


def test_ruff_format_check(rendered_template: Path, template_name: str) -> None:
    _run(
        [sys.executable, "-m", "ruff", "format", "--check", "."],
        cwd=rendered_template,
        label=f"'{template_name}' fails ruff format --check",
    )


def test_ruff_check(rendered_template: Path, template_name: str) -> None:
    _run(
        [sys.executable, "-m", "ruff", "check", "."],
        cwd=rendered_template,
        label=f"'{template_name}' fails ruff check",
    )


@pytest.mark.slow
@pytest.mark.skipif(
    sys.platform != "linux",
    reason=(
        "ruff/pyright/pytest results don't vary by host OS; the rendered "
        "template content is what's under test. Running once (ubuntu) "
        "instead of on every CI matrix leg avoids paying the Windows/macOS "
        "Actions billing multiplier for a `uv sync` that behaves the same "
        "everywhere."
    ),
)
def test_under_own_resolved_toolchain(
    rendered_template: Path, template_name: str
) -> None:
    """Slow: needs `uv sync` in the rendered project (dependency install).

    Runs ruff format/check, pytest, and pyright all against that same
    `uv sync`-resolved environment -- the rendered project's own toolchain,
    not this repo's dev/CI-pinned one -- since that's the version a real
    new user actually hits (see module docstring).
    """
    _run(
        ["uv", "sync"], cwd=rendered_template, label=f"'{template_name}' uv sync failed"
    )
    _run(
        ["uv", "run", "ruff", "format", "--check", "."],
        cwd=rendered_template,
        label=f"'{template_name}' fails ruff format --check under its own resolved ruff",
    )
    _run(
        ["uv", "run", "ruff", "check", "."],
        cwd=rendered_template,
        label=f"'{template_name}' fails ruff check under its own resolved ruff",
    )
    _run(
        ["uv", "run", "pytest"],
        cwd=rendered_template,
        label=f"'{template_name}' pytest failed",
    )
    _run(
        ["uv", "run", "--with", "pyright", "pyright"],
        cwd=rendered_template,
        label=f"'{template_name}' pyright failed",
    )
