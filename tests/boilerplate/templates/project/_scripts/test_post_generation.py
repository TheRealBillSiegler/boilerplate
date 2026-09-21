"""Tests for the generated project's post-generation script.

``post_generation.py`` ships as template content under
``_scripts/`` and is copied verbatim into every generated project, so it is
not part of the importable ``boilerplate`` package. It is loaded here by file
path and exercised directly.
"""

import importlib.util
import io
import subprocess
import types
from pathlib import Path

import pytest
from pytest_mock import MockerFixture
from rich.console import Console

import boilerplate

SCRIPT_PATH = (
    Path(boilerplate.__file__).parent
    / "templates"
    / "project"
    / "_scripts"
    / "post_generation.py"
)


def _load_module() -> types.ModuleType:
    """Load ``post_generation.py`` fresh from its on-disk path."""
    spec = importlib.util.spec_from_file_location(
        "post_generation_under_test", SCRIPT_PATH
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def pg(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    """Load a fresh post_generation module with deterministic, captured output.

    Rich features (status spinners) are disabled and the console is redirected
    to an in-memory buffer so tests can assert on printed text without
    ANSI/animation noise.
    """
    module = _load_module()
    monkeypatch.setattr(module, "use_rich_features", False)
    monkeypatch.setattr(
        module,
        "console",
        Console(file=io.StringIO(), no_color=True, force_terminal=False),
    )
    return module


class TestCheckUv:
    """`check_uv` is the only hard-exit gate reached on end-user machines."""

    def test_exits_with_install_command_when_uv_missing(
        self, pg: types.ModuleType, mocker: MockerFixture
    ) -> None:
        mocker.patch.object(pg.shutil, "which", return_value=None)

        with pytest.raises(SystemExit) as exc_info:
            pg.check_uv()

        assert exc_info.value.code == 1
        assert "astral.sh/uv/install.ps1" in pg.console.file.getvalue()

    def test_does_not_exit_when_uv_present(
        self, pg: types.ModuleType, mocker: MockerFixture
    ) -> None:
        mocker.patch.object(pg.shutil, "which", return_value="/usr/bin/uv")

        pg.check_uv()  # must not raise


class TestRunCommand:
    """`run_command` decodes subprocess output as explicit UTF-8."""

    def test_decodes_output_as_explicit_utf8(
        self, pg: types.ModuleType, mocker: MockerFixture
    ) -> None:
        fake_result = subprocess.CompletedProcess(
            args="echo hi", returncode=0, stdout="hi", stderr=""
        )
        run_mock = mocker.patch.object(pg.subprocess, "run", return_value=fake_result)

        assert pg.run_command("echo hi") is True

        _, kwargs = run_mock.call_args
        assert kwargs["encoding"] == "utf-8"
        assert kwargs["errors"] == "replace"

    def test_retries_then_fails_without_raising(
        self, pg: types.ModuleType, mocker: MockerFixture
    ) -> None:
        error = subprocess.CalledProcessError(1, "false", stderr="boom")
        mocker.patch.object(pg.subprocess, "run", side_effect=error)
        mocker.patch.object(pg.time, "sleep")

        assert pg.run_command("false", max_retries=2, retry_delay=0) is False


class TestSetupEnvironment:
    """`setup_environment` (uv sync) reports real success/failure, not swallowing it."""

    def test_returns_true_when_uv_sync_succeeds(
        self, pg: types.ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(pg, "run_command", lambda *_a, **_k: True)

        assert pg.setup_environment() is True

    def test_returns_false_when_uv_sync_fails(
        self, pg: types.ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(pg, "run_command", lambda *_a, **_k: False)

        assert pg.setup_environment() is False


class TestInitializeGit:
    """`initialize_git` reports real success/failure, not swallowing it."""

    def test_returns_true_when_repo_already_exists(
        self, pg: types.ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)

        assert pg.initialize_git() is True

    def test_returns_true_when_git_init_succeeds(
        self, pg: types.ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(pg, "run_command", lambda *_a, **_k: True)
        monkeypatch.setattr(pg, "print_remote_instructions", lambda: None)

        assert pg.initialize_git() is True

    def test_returns_false_when_git_init_fails(
        self, pg: types.ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(pg, "run_command", lambda *_a, **_k: False)

        assert pg.initialize_git() is False


class TestCleanupScriptsDir:
    """Cleanup is cosmetic: a failure raises instead of exiting the process.

    This lets the caller's warn-and-continue handling run.
    """

    def test_failure_raises_instead_of_exiting_the_process(
        self, pg: types.ModuleType, mocker: MockerFixture
    ) -> None:
        mocker.patch.object(pg.shutil, "rmtree", side_effect=OSError("locked"))

        with pytest.raises(OSError):
            pg.cleanup_scripts_dir()


class TestPostGeneration:
    """End-to-end summary/exit-code behavior of the task orchestrator."""

    def test_all_tasks_succeed_reports_success_without_exiting(
        self, pg: types.ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(pg, "check_uv", lambda: None)
        monkeypatch.setattr(pg, "setup_environment", lambda: True)
        monkeypatch.setattr(pg, "initialize_git", lambda: True)
        monkeypatch.setattr(pg, "cleanup_scripts_dir", lambda: None)

        pg.post_generation()

        assert "All tasks completed successfully!" in pg.console.file.getvalue()

    def test_uv_sync_failure_is_visible_in_summary_and_exit_code(
        self, pg: types.ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(pg, "check_uv", lambda: None)
        monkeypatch.setattr(pg, "setup_environment", lambda: False)
        monkeypatch.setattr(pg, "initialize_git", lambda: True)
        monkeypatch.setattr(pg, "cleanup_scripts_dir", lambda: None)

        with pytest.raises(SystemExit) as exc_info:
            pg.post_generation()

        assert exc_info.value.code != 0
        output = pg.console.file.getvalue()
        assert "All tasks completed successfully!" not in output
        assert "Setup completed with issues" in output

    def test_git_init_failure_is_visible_in_summary_and_exit_code(
        self, pg: types.ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(pg, "check_uv", lambda: None)
        monkeypatch.setattr(pg, "setup_environment", lambda: True)
        monkeypatch.setattr(pg, "initialize_git", lambda: False)
        monkeypatch.setattr(pg, "cleanup_scripts_dir", lambda: None)

        with pytest.raises(SystemExit) as exc_info:
            pg.post_generation()

        assert exc_info.value.code != 0
        output = pg.console.file.getvalue()
        assert "All tasks completed successfully!" not in output
        assert "Setup completed with issues" in output

    def test_cleanup_failure_alone_does_not_fail_the_render(
        self, pg: types.ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(pg, "check_uv", lambda: None)
        monkeypatch.setattr(pg, "setup_environment", lambda: True)
        monkeypatch.setattr(pg, "initialize_git", lambda: True)

        def _raise() -> None:
            raise OSError("locked")

        monkeypatch.setattr(pg, "cleanup_scripts_dir", _raise)

        pg.post_generation()  # must not raise SystemExit

        output = pg.console.file.getvalue()
        assert "Cleanup encountered issues" in output
        assert "minor issues" in output

    def test_keyboard_interrupt_exits_1(
        self, pg: types.ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _raise() -> None:
            raise KeyboardInterrupt

        monkeypatch.setattr(pg, "check_uv", _raise)

        with pytest.raises(SystemExit) as exc_info:
            pg.post_generation()

        assert exc_info.value.code == 1
        assert "interrupted by the user" in pg.console.file.getvalue()

    def test_unhandled_exception_exits_1(
        self, pg: types.ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _raise() -> None:
            raise RuntimeError("boom")

        monkeypatch.setattr(pg, "check_uv", _raise)

        with pytest.raises(SystemExit) as exc_info:
            pg.post_generation()

        assert exc_info.value.code == 1
        assert "Critical error during setup" in pg.console.file.getvalue()
