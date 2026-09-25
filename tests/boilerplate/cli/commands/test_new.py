"""Tests for `boilerplate new` command."""

import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from pytest_mock import MockerFixture
from typer.testing import CliRunner

from boilerplate.cli import app
from boilerplate.cli.commands.new import (
    _load_data_file,  # pyright: ignore[reportPrivateUsage]
    _parse_data_entries,  # pyright: ignore[reportPrivateUsage]
    _resolve_data,  # pyright: ignore[reportPrivateUsage]
    _stdin_is_real_console,  # pyright: ignore[reportPrivateUsage]
    _stdin_supports_prompts,  # pyright: ignore[reportPrivateUsage]
)
from boilerplate.cli.seams import Seams
from boilerplate.common.exceptions import InvalidDataError
from boilerplate.composition.rendering.renderer import Renderer
from boilerplate.constants import ExitCode


def _invoke_and_capture_execution_ctx(
    typer_cli_runner: CliRunner,
    fake_template_dir: Path,
    temp_project_dir: Path,
    renderer: Renderer,
    seams: Seams,
    cli_args: list[str],
) -> object:
    """Invoke `new` and return the ExecutionContext the renderer received."""
    full_args = [
        *cli_args,
        str(temp_project_dir),
        "--templates-dir",
        str(fake_template_dir),
    ]
    result = typer_cli_runner.invoke(app, full_args, obj=seams)
    assert result.exit_code == ExitCode.SUCCESS, result.output

    assert len(renderer.calls) == 1, "renderer.render was not called exactly once"
    return renderer.calls[-1][1]  # Second element of the tuple is ExecutionContext


class TestParseDataEntries:
    """``_parse_data_entries`` turns repeatable key=value into a dict."""

    def test_none_yields_empty_dict(self) -> None:
        assert _parse_data_entries(None) == {}

    def test_empty_list_yields_empty_dict(self) -> None:
        assert _parse_data_entries([]) == {}

    def test_single_entry(self) -> None:
        assert _parse_data_entries(["project_name=my-app"]) == {
            "project_name": "my-app"
        }

    def test_multiple_entries(self) -> None:
        result = _parse_data_entries(["a=1", "b=2"])
        assert result == {"a": "1", "b": "2"}

    def test_value_may_contain_equals(self) -> None:
        """Only the first ``=`` splits key from value."""
        assert _parse_data_entries(["url=https://x/y?a=b"]) == {
            "url": "https://x/y?a=b"
        }

    def test_repeated_key_last_one_wins(self) -> None:
        assert _parse_data_entries(["a=1", "a=2"]) == {"a": "2"}

    def test_entry_without_equals_raises(self) -> None:
        with pytest.raises(InvalidDataError, match="project_name"):
            _parse_data_entries(["project_name"])

    def test_malformed_entry_error_has_data_error_code(self) -> None:
        with pytest.raises(InvalidDataError) as exc_info:
            _parse_data_entries(["nope"])
        assert exc_info.value.error_code == "BP_INPUT_DATA_INVALID"

    def test_empty_key_raises(self) -> None:
        with pytest.raises(InvalidDataError, match="expected key=value"):
            _parse_data_entries(["=value"])

    def test_whitespace_only_key_raises(self) -> None:
        with pytest.raises(InvalidDataError, match="expected key=value"):
            _parse_data_entries(["  =value"])

    def test_underscore_prefixed_key_raises(self) -> None:
        with pytest.raises(InvalidDataError, match="_folder_name"):
            _parse_data_entries(["_folder_name=x"])

    def test_underscore_prefixed_key_error_has_data_error_code(self) -> None:
        with pytest.raises(InvalidDataError) as exc_info:
            _parse_data_entries(["_folder_name=x"])
        assert exc_info.value.error_code == "BP_INPUT_DATA_INVALID"


class TestLoadDataFile:
    """``_load_data_file`` reads a ``--data-file`` YAML mapping as UTF-8."""

    def test_none_path_yields_empty_dict(self) -> None:
        assert _load_data_file(None) == {}

    def test_reads_mapping_as_utf8(self, tmp_path: Path) -> None:
        path = tmp_path / "answers.yml"
        path.write_text("project_name: café\nauthor: Jane\n", encoding="utf-8")
        assert _load_data_file(path) == {"project_name": "café", "author": "Jane"}

    def test_empty_file_yields_empty_dict(self, tmp_path: Path) -> None:
        path = tmp_path / "answers.yml"
        path.write_text("", encoding="utf-8")
        assert _load_data_file(path) == {}

    def test_missing_file_raises_invalid_data_error(self, tmp_path: Path) -> None:
        missing = tmp_path / "does-not-exist.yml"
        with pytest.raises(InvalidDataError, match="Cannot read"):
            _load_data_file(missing)

    def test_missing_file_error_has_data_error_code(self, tmp_path: Path) -> None:
        missing = tmp_path / "does-not-exist.yml"
        with pytest.raises(InvalidDataError) as exc_info:
            _load_data_file(missing)
        assert exc_info.value.error_code == "BP_INPUT_DATA_INVALID"

    def test_non_utf8_file_raises_invalid_data_error(self, tmp_path: Path) -> None:
        path = tmp_path / "answers.yml"
        path.write_bytes(b"\xff\xfe\x00broken")
        with pytest.raises(InvalidDataError, match="Cannot read") as exc_info:
            _load_data_file(path)
        assert exc_info.value.error_code == "BP_INPUT_DATA_INVALID"

    def test_empty_key_raises_invalid_data_error(self, tmp_path: Path) -> None:
        path = tmp_path / "answers.yml"
        path.write_text('"": value\n', encoding="utf-8")
        with pytest.raises(InvalidDataError, match="empty key"):
            _load_data_file(path)

    def test_underscore_prefixed_key_raises_invalid_data_error(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "answers.yml"
        path.write_text("_folder_name: x\n", encoding="utf-8")
        with pytest.raises(InvalidDataError, match="_folder_name"):
            _load_data_file(path)

    def test_non_string_key_raises_invalid_data_error(self, tmp_path: Path) -> None:
        """YAML 1.1 coerces the unquoted key `on` to the boolean True."""
        path = tmp_path / "answers.yml"
        path.write_text("on: bash\n", encoding="utf-8")
        with pytest.raises(InvalidDataError, match="not a string") as exc_info:
            _load_data_file(path)
        assert exc_info.value.error_code == "BP_INPUT_DATA_INVALID"

    def test_malformed_yaml_raises_invalid_data_error(self, tmp_path: Path) -> None:
        path = tmp_path / "answers.yml"
        path.write_text("a: [unclosed\n", encoding="utf-8")
        with pytest.raises(InvalidDataError, match="not valid YAML"):
            _load_data_file(path)

    def test_non_mapping_yaml_raises_invalid_data_error(self, tmp_path: Path) -> None:
        path = tmp_path / "answers.yml"
        path.write_text("- one\n- two\n", encoding="utf-8")
        with pytest.raises(InvalidDataError, match="mapping"):
            _load_data_file(path)

    def test_scalar_yaml_raises_invalid_data_error(self, tmp_path: Path) -> None:
        path = tmp_path / "answers.yml"
        path.write_text("just a string\n", encoding="utf-8")
        with pytest.raises(InvalidDataError, match="mapping"):
            _load_data_file(path)


class TestResolveData:
    """``_resolve_data`` merges ``--data-file`` and ``--data``, ``--data`` wins."""

    def test_both_absent_yields_empty_dict(self) -> None:
        assert _resolve_data(None, None) == {}

    def test_data_only(self) -> None:
        assert _resolve_data(["a=1"], None) == {"a": "1"}

    def test_data_file_only(self, tmp_path: Path) -> None:
        path = tmp_path / "answers.yml"
        path.write_text("a: 1\nb: 2\n", encoding="utf-8")
        assert _resolve_data(None, path) == {"a": 1, "b": 2}

    def test_data_wins_on_collision(self, tmp_path: Path) -> None:
        path = tmp_path / "answers.yml"
        path.write_text("a: from-file\nb: kept\n", encoding="utf-8")
        result = _resolve_data(["a=from-flag"], path)
        assert result == {"a": "from-flag", "b": "kept"}


@pytest.mark.usefixtures("interactive_tty")
def test_new_rejects_a_missing_templates_directory(
    typer_cli_runner: CliRunner, tmp_path: Path
) -> None:
    """A --templates-dir that does not exist stops the command before any render."""
    missing = tmp_path / "nonexistent"

    result = typer_cli_runner.invoke(
        app, ["new", "foo", str(tmp_path / "dest"), "--templates-dir", str(missing)]
    )

    assert result.exit_code == ExitCode.CONFIG_ERROR, result.output
    # Rich hard-wraps output at console width, which can split the message.
    assert "does not exist" in " ".join(result.output.split())


@pytest.mark.parametrize(
    "cli_args, expected",
    [
        (
            # Default interactive, no force
            ["new", "mytpl"],
            {"interactive": True, "overwrite": False},
        ),
        (
            # Non-interactive disables prompts
            ["new", "mytpl", "--non-interactive"],
            {"interactive": False, "overwrite": False},
        ),
        (
            # Force overwrite with a pinned version
            ["new", "mytpl@1.0.0", "--force"],
            {"interactive": True, "overwrite": True},
        ),
        (
            # Non-interactive + force + pinned version
            ["new", "mytpl@1.0.0", "--non-interactive", "--force"],
            {"interactive": False, "overwrite": True},
        ),
    ],
)
@pytest.mark.usefixtures("interactive_tty")
def test_new_flag_to_options_mapping(
    typer_cli_runner: CliRunner,
    fake_template_dir: Path,
    temp_project_dir: Path,
    renderer: Renderer,
    seams: Seams,
    cli_args: list[str],
    expected: dict[str, object],
) -> None:
    """Validates that CLI flags map to ExecutionContext arguments on the renderer."""
    # Add explicit dirs/paths to keep environment-independent
    full_args = [
        *cli_args,
        str(temp_project_dir),  # positional destination argument
        "--templates-dir",
        str(fake_template_dir),
    ]
    result = typer_cli_runner.invoke(app, full_args, obj=seams)

    assert result.exit_code == ExitCode.SUCCESS, result.output

    # Verify the render call with ExecutionContext containing expected parameters
    assert len(renderer.calls) == 1
    execution_ctx = renderer.calls[-1][1]
    assert execution_ctx.interactive is expected["interactive"]
    assert execution_ctx.overwrite is expected["overwrite"]


@pytest.mark.usefixtures("interactive_tty")
def test_new_announces_render_only_when_non_interactive(
    typer_cli_runner: CliRunner,
    fake_template_dir: Path,
    temp_project_dir: Path,
    seams: Seams,
) -> None:
    """Print the render announcement only when nothing is asked first."""
    common = [str(temp_project_dir), "--templates-dir", str(fake_template_dir)]

    interactive = typer_cli_runner.invoke(app, ["new", "mytpl", *common], obj=seams)
    assert interactive.exit_code == ExitCode.SUCCESS, interactive.output
    assert "Rendering to" not in interactive.output

    non_interactive = typer_cli_runner.invoke(
        app, ["new", "mytpl", "--non-interactive", *common], obj=seams
    )
    assert non_interactive.exit_code == ExitCode.SUCCESS, non_interactive.output
    assert "Rendering to" in non_interactive.output


@pytest.mark.usefixtures("interactive_tty")
def test_new_handles_render_failure_behavior(
    typer_cli_runner: CliRunner,
    fake_template_dir: Path,
    temp_project_dir: Path,
    renderer: Renderer,
    seams: Seams,
) -> None:
    """Tests that render failures are properly propagated to user."""
    renderer.error = RuntimeError("copy failed")  # pyright: ignore[reportAttributeAccessIssue]
    result = typer_cli_runner.invoke(
        app,
        [
            "new",
            "mytpl",
            str(temp_project_dir),
            "--templates-dir",
            str(fake_template_dir),
        ],
        obj=seams,
    )
    # Focus on behavior: error message propagation
    assert "copy failed" in result.output


@pytest.mark.usefixtures("interactive_tty")
def test_new_default_is_interactive(
    typer_cli_runner: CliRunner,
    fake_template_dir: Path,
    temp_project_dir: Path,
    renderer: Renderer,
    seams: Seams,
) -> None:
    """Interactive mode is enabled by default and creates destination."""
    result = typer_cli_runner.invoke(
        app,
        [
            "new",
            "mytpl",
            str(temp_project_dir),  # positional destination argument
            "--templates-dir",
            str(fake_template_dir),
        ],
        obj=seams,
    )

    assert result.exit_code == ExitCode.SUCCESS, result.output

    # Verify interactive=True by default in ExecutionContext
    assert len(renderer.calls) == 1
    execution_ctx = renderer.calls[-1][1]
    assert execution_ctx.interactive is True


@pytest.mark.usefixtures("interactive_tty")
class TestCiModeAndNoTasks:
    """`--ci` and `--no-tasks` propagate into ExecutionContext as promised."""

    def test_ci_flag_sets_non_interactive_and_leaves_tasks_running(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        temp_project_dir: Path,
        renderer: Renderer,
        seams: Seams,
    ) -> None:
        """`boilerplate --ci new ...` implies `--non-interactive` only."""
        ctx = _invoke_and_capture_execution_ctx(
            typer_cli_runner,
            fake_template_dir,
            temp_project_dir,
            renderer,
            seams,
            ["--ci", "new", "project"],
        )
        assert ctx.interactive is False  # type: ignore[attr-defined]
        assert ctx.skip_tasks is False  # type: ignore[attr-defined]

    def test_no_tasks_flag_alone_sets_skip_tasks(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        temp_project_dir: Path,
        renderer: Renderer,
        seams: Seams,
    ) -> None:
        """`--no-tasks` without `--ci` still propagates to ExecutionContext."""
        ctx = _invoke_and_capture_execution_ctx(
            typer_cli_runner,
            fake_template_dir,
            temp_project_dir,
            renderer,
            seams,
            ["new", "project", "--no-tasks"],
        )
        assert ctx.skip_tasks is True  # type: ignore[attr-defined]
        # --no-tasks alone does not imply non-interactive
        assert ctx.interactive is True  # type: ignore[attr-defined]

    def test_default_has_tasks_enabled(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        temp_project_dir: Path,
        renderer: Renderer,
        seams: Seams,
    ) -> None:
        """Without any flag, tasks run (skip_tasks=False on ExecutionContext)."""
        ctx = _invoke_and_capture_execution_ctx(
            typer_cli_runner,
            fake_template_dir,
            temp_project_dir,
            renderer,
            seams,
            ["new", "project"],
        )
        assert ctx.skip_tasks is False  # type: ignore[attr-defined]

    def test_ci_env_var_alone_sets_non_interactive_and_leaves_tasks_running(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        temp_project_dir: Path,
        renderer: Renderer,
        seams: Seams,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """BOILERPLATE_CI=1 matches --ci: --non-interactive only, tasks still run."""
        monkeypatch.setenv("BOILERPLATE_CI", "1")
        ctx = _invoke_and_capture_execution_ctx(
            typer_cli_runner,
            fake_template_dir,
            temp_project_dir,
            renderer,
            seams,
            ["new", "project"],
        )
        assert ctx.interactive is False  # type: ignore[attr-defined]
        assert ctx.skip_tasks is False  # type: ignore[attr-defined]


class TestNonInteractiveEnvVar:
    """``BOILERPLATE_NON_INTERACTIVE`` joins ``--non-interactive`` with OR semantics."""

    def test_env_var_alone_behaves_like_flag(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        temp_project_dir: Path,
        renderer: Renderer,
        seams: Seams,
        mocker: MockerFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """No flags, only the env var — this proves non-TTY guard is bypassed."""
        mocker.patch(
            "boilerplate.cli.commands.new._stdin_supports_prompts",
            return_value=False,
        )
        monkeypatch.setenv("BOILERPLATE_NON_INTERACTIVE", "1")

        ctx = _invoke_and_capture_execution_ctx(
            typer_cli_runner,
            fake_template_dir,
            temp_project_dir,
            renderer,
            seams,
            ["new", "project"],
        )
        assert ctx.interactive is False  # type: ignore[attr-defined]
        # BOILERPLATE_NON_INTERACTIVE affects only non_interactive, never the CI chain.
        assert ctx.skip_tasks is False  # type: ignore[attr-defined]

    def test_env_var_garbage_value_is_truthy(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        temp_project_dir: Path,
        renderer: Renderer,
        seams: Seams,
        mocker: MockerFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A garbage value like 'banana' is truthy per the spec's truthiness rule."""
        mocker.patch(
            "boilerplate.cli.commands.new._stdin_supports_prompts",
            return_value=False,
        )
        monkeypatch.setenv("BOILERPLATE_NON_INTERACTIVE", "banana")

        ctx = _invoke_and_capture_execution_ctx(
            typer_cli_runner,
            fake_template_dir,
            temp_project_dir,
            renderer,
            seams,
            ["new", "project"],
        )
        assert ctx.interactive is False  # type: ignore[attr-defined]

    @pytest.mark.usefixtures("interactive_tty")
    @pytest.mark.parametrize("value", ["0", "false", "FALSE"])
    def test_env_var_zero_or_false_behaves_as_unset(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        temp_project_dir: Path,
        renderer: Renderer,
        seams: Seams,
        monkeypatch: pytest.MonkeyPatch,
        value: str,
    ) -> None:
        monkeypatch.setenv("BOILERPLATE_NON_INTERACTIVE", value)

        ctx = _invoke_and_capture_execution_ctx(
            typer_cli_runner,
            fake_template_dir,
            temp_project_dir,
            renderer,
            seams,
            ["new", "project"],
        )
        assert ctx.interactive is True  # type: ignore[attr-defined]

    def test_flag_and_env_var_compose(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        temp_project_dir: Path,
        renderer: Renderer,
        seams: Seams,
        mocker: MockerFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The flag alone forces non-interactive; env var too stays idempotent."""
        mocker.patch(
            "boilerplate.cli.commands.new._stdin_supports_prompts",
            return_value=False,
        )
        monkeypatch.setenv("BOILERPLATE_NON_INTERACTIVE", "1")

        ctx = _invoke_and_capture_execution_ctx(
            typer_cli_runner,
            fake_template_dir,
            temp_project_dir,
            renderer,
            seams,
            ["new", "project", "--non-interactive"],
        )
        assert ctx.interactive is False  # type: ignore[attr-defined]
        # BOILERPLATE_NON_INTERACTIVE affects only non_interactive, never the CI chain.
        assert ctx.skip_tasks is False  # type: ignore[attr-defined]

    def test_generic_ci_env_var_is_a_no_op(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        temp_project_dir: Path,
        renderer: Renderer,
        seams: Seams,
        mocker: MockerFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Regression: generic CI=true does not switch input mode (see ADR-013)."""
        mocker.patch(
            "boilerplate.cli.commands.new._stdin_supports_prompts",
            return_value=False,
        )
        monkeypatch.setenv("CI", "true")

        result = typer_cli_runner.invoke(
            app,
            [
                "new",
                "mytpl",
                str(temp_project_dir),
                "--templates-dir",
                str(fake_template_dir),
            ],
            obj=seams,
        )

        assert result.exit_code == ExitCode.VALIDATION_ERROR
        assert "BP_INPUT_TTY_REQUIRED" in result.output
        assert not renderer.calls


@pytest.mark.usefixtures("interactive_tty")
class TestDataFlagsCliWiring:
    """`--data`/`--data-file` reach `ExecutionContext.context_data`."""

    def test_data_flag_populates_context_data(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        temp_project_dir: Path,
        renderer: Renderer,
        seams: Seams,
    ) -> None:
        ctx = _invoke_and_capture_execution_ctx(
            typer_cli_runner,
            fake_template_dir,
            temp_project_dir,
            renderer,
            seams,
            ["new", "project", "--data", "project_name=my-app"],
        )
        assert ctx.context_data == {"project_name": "my-app"}  # type: ignore[attr-defined]

    def test_repeated_data_flags_merge(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        temp_project_dir: Path,
        renderer: Renderer,
        seams: Seams,
    ) -> None:
        ctx = _invoke_and_capture_execution_ctx(
            typer_cli_runner,
            fake_template_dir,
            temp_project_dir,
            renderer,
            seams,
            ["new", "project", "--data", "a=1", "--data", "b=2"],
        )
        assert ctx.context_data == {"a": "1", "b": "2"}  # type: ignore[attr-defined]

    def test_data_file_flag_populates_context_data(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        temp_project_dir: Path,
        renderer: Renderer,
        seams: Seams,
        tmp_path: Path,
    ) -> None:
        data_file = tmp_path / "answers.yml"
        data_file.write_text("project_name: from-file\n", encoding="utf-8")
        ctx = _invoke_and_capture_execution_ctx(
            typer_cli_runner,
            fake_template_dir,
            temp_project_dir,
            renderer,
            seams,
            ["new", "project", "--data-file", str(data_file)],
        )
        assert ctx.context_data == {"project_name": "from-file"}  # type: ignore[attr-defined]

    def test_data_wins_over_data_file_on_collision(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        temp_project_dir: Path,
        renderer: Renderer,
        seams: Seams,
        tmp_path: Path,
    ) -> None:
        data_file = tmp_path / "answers.yml"
        data_file.write_text(
            "project_name: from-file\nauthor: kept\n", encoding="utf-8"
        )
        ctx = _invoke_and_capture_execution_ctx(
            typer_cli_runner,
            fake_template_dir,
            temp_project_dir,
            renderer,
            seams,
            [
                "new",
                "project",
                "--data-file",
                str(data_file),
                "--data",
                "project_name=from-flag",
            ],
        )
        assert ctx.context_data == {  # type: ignore[attr-defined]
            "project_name": "from-flag",
            "author": "kept",
        }

    def test_no_data_flags_yields_empty_context_data(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        temp_project_dir: Path,
        renderer: Renderer,
        seams: Seams,
    ) -> None:
        ctx = _invoke_and_capture_execution_ctx(
            typer_cli_runner,
            fake_template_dir,
            temp_project_dir,
            renderer,
            seams,
            ["new", "project"],
        )
        assert ctx.context_data == {}  # type: ignore[attr-defined]


class TestDataFlagsFailureModes:
    """Malformed `--data`/`--data-file` input fails closed at exit code 3.

    Uses the real CLI error boundary (no mocked exception handling) so the
    assertions cover the whole path: parse failure -> InvalidDataError ->
    cli_error_handler -> ExitCode.VALIDATION_ERROR with the BP_* code and a
    message naming the problem.
    """

    def test_malformed_data_entry_exits_validation_error(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        temp_project_dir: Path,
        renderer: Renderer,
        seams: Seams,
    ) -> None:
        result = typer_cli_runner.invoke(
            app,
            [
                "new",
                "mytpl",
                str(temp_project_dir),
                "--data",
                "no-equals-sign",
                "--non-interactive",
                "--templates-dir",
                str(fake_template_dir),
            ],
            obj=seams,
        )

        assert result.exit_code == ExitCode.VALIDATION_ERROR
        assert "BP_INPUT_DATA_INVALID" in result.output
        assert not renderer.calls

    def test_missing_data_file_exits_validation_error(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        temp_project_dir: Path,
        tmp_path: Path,
        renderer: Renderer,
        seams: Seams,
    ) -> None:
        missing = tmp_path / "does-not-exist.yml"

        result = typer_cli_runner.invoke(
            app,
            [
                "new",
                "mytpl",
                str(temp_project_dir),
                "--data-file",
                str(missing),
                "--non-interactive",
                "--templates-dir",
                str(fake_template_dir),
            ],
            obj=seams,
        )

        assert result.exit_code == ExitCode.VALIDATION_ERROR
        assert "BP_INPUT_DATA_INVALID" in result.output
        assert not renderer.calls

    def test_non_mapping_data_file_exits_validation_error(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        temp_project_dir: Path,
        tmp_path: Path,
        renderer: Renderer,
        seams: Seams,
    ) -> None:
        data_file = tmp_path / "answers.yml"
        data_file.write_text("- one\n- two\n", encoding="utf-8")

        result = typer_cli_runner.invoke(
            app,
            [
                "new",
                "mytpl",
                str(temp_project_dir),
                "--data-file",
                str(data_file),
                "--non-interactive",
                "--templates-dir",
                str(fake_template_dir),
            ],
            obj=seams,
        )

        assert result.exit_code == ExitCode.VALIDATION_ERROR
        assert "BP_INPUT_DATA_INVALID" in result.output
        assert not renderer.calls

    def test_invalid_yaml_data_file_exits_validation_error(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        temp_project_dir: Path,
        tmp_path: Path,
        renderer: Renderer,
        seams: Seams,
    ) -> None:
        data_file = tmp_path / "answers.yml"
        data_file.write_text("a: [unclosed\n", encoding="utf-8")

        result = typer_cli_runner.invoke(
            app,
            [
                "new",
                "mytpl",
                str(temp_project_dir),
                "--data-file",
                str(data_file),
                "--non-interactive",
                "--templates-dir",
                str(fake_template_dir),
            ],
            obj=seams,
        )

        assert result.exit_code == ExitCode.VALIDATION_ERROR
        assert "BP_INPUT_DATA_INVALID" in result.output
        assert not renderer.calls

    def test_underscore_prefixed_data_key_exits_validation_error(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        temp_project_dir: Path,
        renderer: Renderer,
        seams: Seams,
    ) -> None:
        result = typer_cli_runner.invoke(
            app,
            [
                "new",
                "mytpl",
                str(temp_project_dir),
                "--data",
                "_folder_name=x",
                "--non-interactive",
                "--templates-dir",
                str(fake_template_dir),
            ],
            obj=seams,
        )

        assert result.exit_code == ExitCode.VALIDATION_ERROR
        assert "BP_INPUT_DATA_INVALID" in result.output
        assert not renderer.calls

    def test_dry_run_with_malformed_data_entry_exits_validation_error(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        temp_project_dir: Path,
        renderer: Renderer,
        seams: Seams,
    ) -> None:
        """Regression: --dry-run does not skip --data/--data-file validation."""
        result = typer_cli_runner.invoke(
            app,
            [
                "new",
                "mytpl",
                str(temp_project_dir),
                "--dry-run",
                "--data",
                "no-equals-sign",
                "--templates-dir",
                str(fake_template_dir),
            ],
            obj=seams,
        )

        assert result.exit_code == ExitCode.VALIDATION_ERROR
        assert "BP_INPUT_DATA_INVALID" in result.output
        assert not renderer.calls

    def test_dry_run_with_missing_data_file_exits_validation_error(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        temp_project_dir: Path,
        tmp_path: Path,
        renderer: Renderer,
        seams: Seams,
    ) -> None:
        """Regression: --dry-run does not skip --data/--data-file validation."""
        missing = tmp_path / "does-not-exist.yml"

        result = typer_cli_runner.invoke(
            app,
            [
                "new",
                "mytpl",
                str(temp_project_dir),
                "--dry-run",
                "--data-file",
                str(missing),
                "--templates-dir",
                str(fake_template_dir),
            ],
            obj=seams,
        )

        assert result.exit_code == ExitCode.VALIDATION_ERROR
        assert "BP_INPUT_DATA_INVALID" in result.output
        assert not renderer.calls


class TestNonTtyGuard:
    """Interactive mode without a TTY fails closed before any render starts.

    Regression guard: without the pre-flight, Copier's prompt layer can
    retry-loop on EOF under a non-TTY stdin and grow memory without bound.
    """

    def test_interactive_without_tty_fails_closed(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        temp_project_dir: Path,
        renderer: Renderer,
        seams: Seams,
        mocker: MockerFixture,
    ) -> None:
        mocker.patch(
            "boilerplate.cli.commands.new._stdin_supports_prompts",
            return_value=False,
        )

        result = typer_cli_runner.invoke(
            app,
            [
                "new",
                "mytpl",
                str(temp_project_dir),
                "--templates-dir",
                str(fake_template_dir),
            ],
            obj=seams,
        )

        assert result.exit_code == ExitCode.VALIDATION_ERROR
        assert "BP_INPUT_TTY_REQUIRED" in result.output
        assert "--non-interactive" in result.output
        assert not renderer.calls

    def test_non_interactive_flag_bypasses_guard(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        temp_project_dir: Path,
        renderer: Renderer,
        seams: Seams,
        mocker: MockerFixture,
    ) -> None:
        mocker.patch(
            "boilerplate.cli.commands.new._stdin_supports_prompts",
            return_value=False,
        )

        result = typer_cli_runner.invoke(
            app,
            [
                "new",
                "mytpl",
                str(temp_project_dir),
                "--non-interactive",
                "--templates-dir",
                str(fake_template_dir),
            ],
            obj=seams,
        )

        assert result.exit_code == ExitCode.SUCCESS, result.output
        assert len(renderer.calls) == 1

    def test_dry_run_without_tty_succeeds(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        temp_project_dir: Path,
        mocker: MockerFixture,
    ) -> None:
        """--dry-run never prompts, so it stays legal in pipes and CI."""
        mocker.patch(
            "boilerplate.cli.commands.new._stdin_supports_prompts",
            return_value=False,
        )

        result = typer_cli_runner.invoke(
            app,
            [
                "new",
                "mytpl",
                str(temp_project_dir),
                "--dry-run",
                "--templates-dir",
                str(fake_template_dir),
            ],
        )

        assert result.exit_code == ExitCode.SUCCESS, result.output
        assert "Dry run" in result.output


class TestDestination:
    """The current directory is never assumed; a render needs a named destination.

    docs/design/05-cli-reference.md, Destination behavior: provided or
    prompted, and non-interactive without one exits 3.
    """

    def test_non_interactive_without_destination_exits_validation_error(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        renderer: Renderer,
        seams: Seams,
    ) -> None:
        result = typer_cli_runner.invoke(
            app,
            [
                "new",
                "mytpl",
                "--non-interactive",
                "--templates-dir",
                str(fake_template_dir),
            ],
            obj=seams,
        )

        assert result.exit_code == ExitCode.VALIDATION_ERROR, result.output
        assert "destination is required in non-interactive mode" in result.output
        assert "BP_INPUT_DEST_REQUIRED" in result.output
        assert not renderer.calls

    def test_ci_without_destination_exits_validation_error(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        renderer: Renderer,
        seams: Seams,
    ) -> None:
        result = typer_cli_runner.invoke(
            app,
            ["--ci", "new", "mytpl", "--templates-dir", str(fake_template_dir)],
            obj=seams,
        )

        assert result.exit_code == ExitCode.VALIDATION_ERROR, result.output
        assert not renderer.calls

    @pytest.mark.usefixtures("interactive_tty")
    def test_interactive_without_destination_prompts_for_it(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        temp_project_dir: Path,
        renderer: Renderer,
        seams: Seams,
    ) -> None:
        result = typer_cli_runner.invoke(
            app,
            ["new", "mytpl", "--templates-dir", str(fake_template_dir)],
            input=f"{temp_project_dir}\n",
            obj=seams,
        )

        assert result.exit_code == ExitCode.SUCCESS, result.output
        execution_ctx = renderer.calls[-1][1]
        assert execution_ctx.destination == temp_project_dir

    def test_dry_run_without_destination_reports_the_working_directory(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        mocker: MockerFixture,
    ) -> None:
        mocker.patch(
            "boilerplate.cli.commands.new._stdin_supports_prompts",
            return_value=False,
        )

        result = typer_cli_runner.invoke(
            app,
            ["new", "mytpl", "--dry-run", "--templates-dir", str(fake_template_dir)],
        )

        assert result.exit_code == ExitCode.SUCCESS, result.output
        assert "Dry run" in result.output
        # Dry run: "would create . from <layers>" when no destination is given.
        assert "create ." in " ".join(result.output.split())

    @pytest.mark.parametrize(
        ("args", "literal"),
        [
            pytest.param(
                ["mytpl", "[bold]dest"], "create [bold]dest", id="destination"
            ),
            pytest.param(
                ["[bold]mytpl", "dest"], "Resolving [bold]mytpl", id="template"
            ),
            pytest.param(
                ["[/bold]mytpl", "dest"],
                "Template not found: [/bold]mytpl",
                id="error-line",
            ),
        ],
    )
    def test_user_supplied_text_prints_as_typed(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        args: list[str],
        literal: str,
    ) -> None:
        """Square brackets in an argument print literally, not as Rich markup.

        Rich reads "[bold]" as a style tag, so parsed as markup it would
        vanish from the line the user reads, and an unmatched "[/bold]" would
        crash the error line instead of printing it.
        """
        result = typer_cli_runner.invoke(
            app,
            ["new", *args, "--dry-run", "--templates-dir", str(fake_template_dir)],
        )

        assert literal in " ".join(result.output.split())


class TestStdinSupportsPrompts:
    """The real seam body: TTY yes/no, absent stdin, and a raising isatty."""

    @pytest.mark.parametrize(
        ("fake_stdin", "expected"),
        [
            pytest.param(SimpleNamespace(isatty=lambda: True), True, id="tty"),
            pytest.param(SimpleNamespace(isatty=lambda: False), False, id="not-tty"),
            pytest.param(None, False, id="absent-stdin"),
        ],
    )
    def test_stdin_states_map_to_prompt_support(
        self, mocker: MockerFixture, fake_stdin: object, expected: bool
    ) -> None:
        mocker.patch("boilerplate.cli.commands.new.sys.stdin", fake_stdin)
        mocker.patch(
            "boilerplate.cli.commands.new._stdin_is_real_console", return_value=True
        )
        assert _stdin_supports_prompts() is expected

    def test_isatty_lie_is_caught_by_console_probe(self, mocker: MockerFixture) -> None:
        """A char device like NUL reports isatty()=True; the probe rejects it."""
        mocker.patch(
            "boilerplate.cli.commands.new.sys.stdin",
            SimpleNamespace(isatty=lambda: True),
        )
        mocker.patch(
            "boilerplate.cli.commands.new._stdin_is_real_console", return_value=False
        )
        assert _stdin_supports_prompts() is False

    def test_console_probe_returns_bool_without_crashing(self) -> None:
        """Smoke checks the platform branch; the value is environment-dependent."""
        assert isinstance(_stdin_is_real_console(), bool)

    def test_closed_stdin_counts_as_no_tty(self, mocker: MockerFixture) -> None:
        """isatty() raises ValueError on a closed stream; the seam fails closed."""

        def _raise_closed() -> bool:
            raise ValueError("I/O operation on closed file")

        mocker.patch(
            "boilerplate.cli.commands.new.sys.stdin",
            SimpleNamespace(isatty=_raise_closed),
        )
        assert _stdin_supports_prompts() is False


class TestFormatOption:
    """An unknown --format value is rejected instead of silently ignored."""

    def test_rejects_an_unknown_format(
        self, typer_cli_runner: CliRunner, tmp_path: Path
    ) -> None:
        result = typer_cli_runner.invoke(
            app, ["new", "project", str(tmp_path), "--format", "xml"]
        )

        assert result.exit_code == ExitCode.VALIDATION_ERROR
        assert "Invalid value for '--format'" in " ".join(
            re.sub(r"\x1b\[[0-9;]*m", "", result.output).split()
        )


class TestYesOptionRemoved:
    """``--yes``/``-y`` only ever implied ``--non-interactive``; use that flag."""

    @pytest.mark.parametrize("flag", ["--yes", "-y"])
    def test_yes_is_rejected_as_an_unknown_option(
        self, typer_cli_runner: CliRunner, tmp_path: Path, flag: str
    ) -> None:
        result = typer_cli_runner.invoke(app, ["new", "project", str(tmp_path), flag])
        output = re.sub(r"\x1b\[[0-9;]*m", "", result.output)

        assert result.exit_code == ExitCode.VALIDATION_ERROR
        assert "No such option" in " ".join(output.split())


class TestDryRunShortFlag:
    """``-n`` is dry run, matching Copier, make, git clean, and rsync.

    ``--non-interactive`` and ``--no-tasks`` are scripted, safety-relevant
    switches and keep long forms only; see docs/design/05-cli-reference.md.
    """

    def test_short_flag_n_behaves_as_dry_run_with_no_destination_needed(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        renderer: Renderer,
        seams: Seams,
        mocker: MockerFixture,
    ) -> None:
        mocker.patch(
            "boilerplate.cli.commands.new._stdin_supports_prompts",
            return_value=False,
        )

        result = typer_cli_runner.invoke(
            app,
            ["new", "mytpl", "-n", "--templates-dir", str(fake_template_dir)],
            obj=seams,
        )

        assert result.exit_code == ExitCode.SUCCESS, result.output
        assert "Dry run" in result.output
        assert not renderer.calls

    def test_short_flag_t_is_rejected_as_an_unknown_option(
        self, typer_cli_runner: CliRunner, tmp_path: Path
    ) -> None:
        result = typer_cli_runner.invoke(app, ["new", "project", str(tmp_path), "-T"])
        output = re.sub(r"\x1b\[[0-9;]*m", "", result.output)

        assert result.exit_code == ExitCode.VALIDATION_ERROR
        assert "No such option" in " ".join(output.split())

    def test_help_gives_n_to_dry_run_and_no_short_form_to_the_scripted_switches(
        self, typer_cli_runner: CliRunner
    ) -> None:
        result = typer_cli_runner.invoke(app, ["new", "--help"])
        output = re.sub(r"\x1b\[[0-9;]*m", "", result.output)

        assert re.search(r"--dry-run\s+-n\b", output)
        assert re.search(r"--non-interactive\s+[A-Za-z]", output)
        assert re.search(r"--no-tasks\s+[A-Za-z]", output)
