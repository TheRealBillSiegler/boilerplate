"""Bundled templates render output that passes the gates their own docs promise.

Two paths, deliberately different cost:

- Fast, no network: every layer renders with ``--no-tasks`` and its output
  passes this repo's own pinned ``ruff check``/``ruff format --check``; the
  ``project`` layer additionally runs its bundled pytest suite in a
  subprocess against this repo's own pytest, over ``PYTHONPATH``, since its
  tests need nothing beyond the standard library and pytest itself.
- Slow (``@pytest.mark.slow``): the ``streamlit`` layer renders with tasks so
  its post-generation ``uv sync`` actually resolves Streamlit and Pydantic,
  then its own pytest suite runs under that resolved environment. This is
  the only path that proves a rendered test module is even collected —
  pytest silently skips a file whose name doesn't match ``test_*.py``
  instead of failing, so a wrong filename passes a bare "exit code 0" check.

Separately, every layer's rendered ``pyproject.toml`` must pass validate-pyproject
and declare ``license``, if at all, in PEP 639's string form.
"""

import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

import pytest
from validate_pyproject import api

from tests.boilerplate.templates.conftest import LAYERS, render


def _run(cmd: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> str:
    """Run `cmd` in `cwd`, failing the test with captured output on error.

    Args:
        cmd: Argv to execute.
        cwd: Working directory for the subprocess.
        env: Environment for the subprocess; inherits the current one when
            omitted.

    Returns:
        Combined stdout and stderr.
    """
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0, f"{' '.join(cmd)} in {cwd}:\n{output}"
    return output


class TestRenderedLayersPassRuffGates:
    """Every bundled layer's rendered output passes this repo's own ruff."""

    @pytest.mark.parametrize("layer", LAYERS, ids=lambda p: p.name)
    def test_ruff_check_passes(self, layer: Path, tmp_path: Path) -> None:
        dest = render(layer.name, tmp_path, skip_tasks=True)
        _run([sys.executable, "-m", "ruff", "check", "--no-fix", "."], cwd=dest)

    @pytest.mark.parametrize("layer", LAYERS, ids=lambda p: p.name)
    def test_ruff_format_check_passes(self, layer: Path, tmp_path: Path) -> None:
        dest = render(layer.name, tmp_path, skip_tasks=True)
        _run([sys.executable, "-m", "ruff", "format", "--check", "."], cwd=dest)


class TestRenderedProjectPytestPasses:
    """The `project` layer's own tests need nothing beyond pytest itself.

    So the fast, no-network path can run them straight from this repo's own
    pytest by pointing `PYTHONPATH` at the rendered `src`, with no `uv sync`.
    """

    @pytest.mark.parametrize(
        ("sample_module", "test_name"),
        [(True, "test_add"), (False, "test_package_imports")],
        ids=["with-sample-module", "without-sample-module"],
    )
    def test_pytest_passes_over_pythonpath(
        self, tmp_path: Path, sample_module: bool, test_name: str
    ) -> None:
        dest = render(
            "project",
            tmp_path,
            context_data={"sample_module": sample_module},
            skip_tasks=True,
        )
        env = {**os.environ, "PYTHONPATH": str(dest / "src")}
        output = _run(
            [sys.executable, "-m", "pytest", str(dest / "tests"), "-v"],
            cwd=dest,
            env=env,
        )
        assert test_name in output


@pytest.mark.slow
class TestRenderedStreamlitPytestPassesUnderItsOwnToolchain:
    """The `streamlit` layer's smoke test needs Streamlit installed to run.

    So this path renders with tasks (the post-generation `uv sync` resolves
    Streamlit and Pydantic into the rendered project's own venv), then runs
    the rendered project's own pytest. Asserting on the specific test names
    (not just a zero exit code) is deliberate: pytest silently skips a file
    whose name doesn't match `test_*.py` rather than failing, so a renamed
    smoke test could pass a bare exit-code check while never running.

    Skipped when `uv` is not on `PATH`, since the post-generation `uv sync`
    this path depends on cannot run without it. When `uv` is present, this
    test still needs network access to resolve Streamlit and Pydantic; CI
    provides that, but an offline local `uv run pytest` will see it fail
    rather than skip.
    """

    def test_pytest_passes_after_uv_sync(self, tmp_path: Path) -> None:
        if shutil.which("uv") is None:
            pytest.skip("uv is not on PATH")
        dest = render("streamlit", tmp_path, skip_tasks=False)
        output = _run(["uv", "run", "pytest", "-v"], cwd=dest)
        assert "test_app_runs_without_exception" in output
        assert "test_invalid_search_shows_a_warning" in output


def _rendered_pyproject(layer: Path, tmp_path: Path) -> dict[str, Any]:
    """Render `layer` without tasks and parse the `pyproject.toml` it writes.

    Args:
        layer: The bundled layer's template directory.
        tmp_path: The test's temporary directory, the render's parent.

    Returns:
        The rendered `pyproject.toml` as a TOML document.
    """
    dest = render(layer.name, tmp_path, skip_tasks=True)
    return tomllib.loads((dest / "pyproject.toml").read_text(encoding="utf-8"))


class TestRenderedPyprojectMeetsThePackagingSpecification:
    """Every bundled layer renders a `pyproject.toml` that meets the packaging spec.

    validate-pyproject checks the PEP 517, 518, 621, 639 and 735 schemas and SPDX
    expression syntax. Its schema still accepts the `license` table PEP 639
    deprecated, so a second test requires the string form whenever the key is set;
    the first test checks that string's SPDX syntax.
    """

    @pytest.mark.parametrize("layer", LAYERS, ids=lambda p: p.name)
    def test_validate_pyproject_accepts_it(self, layer: Path, tmp_path: Path) -> None:
        api.Validator()(_rendered_pyproject(layer, tmp_path))

    @pytest.mark.parametrize("layer", LAYERS, ids=lambda p: p.name)
    def test_license_is_absent_or_a_string(self, layer: Path, tmp_path: Path) -> None:
        project = _rendered_pyproject(layer, tmp_path)["project"]
        assert "license" not in project or isinstance(project["license"], str), (
            f"license must be an SPDX expression string (PEP 639), got {project['license']!r}"
        )
