"""Tests for `boilerplate new` command."""

import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from pytest_mock import MockerFixture
from typer.testing import CliRunner

from boilerplate.cli import app
from boilerplate.cli.commands.new import (
    _apply_ci_mode_and_yes,  # pyright: ignore[reportPrivateUsage]
    _load_data_file,  # pyright: ignore[reportPrivateUsage]
    _parse_data_entries,  # pyright: ignore[reportPrivateUsage]
    _resolve_data,  # pyright: ignore[reportPrivateUsage]
    _stdin_is_real_console,  # pyright: ignore[reportPrivateUsage]
    _stdin_supports_prompts,  # pyright: ignore[reportPrivateUsage]
)
from boilerplate.common.exceptions import BoilerplateError, InvalidDataError
from boilerplate.constants import ExitCode


def _invoke_and_capture_execution_ctx(
    typer_cli_runner: CliRunner,
    fake_template_dir: Path,
    temp_project_dir: Path,
    mocker: MockerFixture,
    cli_args: list[str],
) -> object:
    """Invokes `new` and returns the ExecutionContext passed to RenderEngine."""
    mocker.patch("boilerplate.cli.commands.new.compute_composition")
    mock_render_engine = mocker.patch("boilerplate.cli.commands.new.RenderEngine")

    full_args = [
        *cli_args,
        str(temp_project_dir),
        "--templates-dir",
        str(fake_template_dir),
    ]
    result = typer_cli_runner.invoke(app, full_args)
    assert result.exit_code == ExitCode.SUCCESS, result.output

    render_call = mock_render_engine.return_value.render.call_args
    assert render_call is not None, "RenderEngine.render was not called"
    return render_call[0][1]  # Second positional argument is ExecutionContext


class TestApplyCiModeAndYes:
    """Decision table for ``_apply_ci_mode_and_yes``.

    Encodes the composition rules documented on the helper. If any row below
    surprises you, the rules are either wrong or under-specified — fix both
    the helper and this table together.
    """

    @pytest.mark.parametrize(
        ("ci_mode", "non_interactive", "yes", "no_tasks", "expected"),
        [
            # No flags → defaults off.
            (False, False, False, False, (False, False)),
            # Subcommand flags alone.
            (False, True, False, False, (True, False)),
            (False, False, True, False, (True, False)),
            (False, False, False, True, (False, True)),
            # --yes implies non-interactive; does not imply no-tasks.
            (False, False, True, False, (True, False)),
            # --ci alone implies all four (both tuple elements True).
            (True, False, False, False, (True, True)),
            # --ci with subcommand flags is idempotent.
            (True, True, True, True, (True, True)),
        ],
    )
    def test_composition_rules(
        self,
        *,
        ci_mode: bool,
        non_interactive: bool,
        yes: bool,
        no_tasks: bool,
        expected: tuple[bool, bool],
    ) -> None:
        result = _apply_ci_mode_and_yes(
            ci_mode=ci_mode,
            non_interactive=non_interactive,
            yes=yes,
            no_tasks=no_tasks,
        )
        assert result == expected


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


@pytest.mark.parametrize(
    "error_message,validation_function",
    [
        (
            "does not exist or is invalid",
            "boilerplate.cli.utils.validate_directory",
        ),
    ],
)
@pytest.mark.usefixtures("interactive_tty")
def test_new_validates_template_directory_behavior(
    monkeypatch: pytest.MonkeyPatch,
    typer_cli_runner: CliRunner,
    tmp_path: Path,
    error_message: str,
    validation_function: str,
) -> None:
    """Tests that 'new' command properly calls directory validation."""
    fake_path = tmp_path / "nonexistent"
    validation_calls = []

    def track_validate_directory(p: Path) -> Path:
        validation_calls.append(p)
        if p == fake_path:
            raise BoilerplateError(f"Directory '{p}' {error_message}")
        return p

    monkeypatch.setattr(validation_function, track_validate_directory)

    result = typer_cli_runner.invoke(
        app, ["new", "foo", str(tmp_path / "dest"), "--templates-dir", str(fake_path)]
    )

    # Verify behavior: validator was called with correct path
    assert fake_path in validation_calls, "Directory validation should be called"
    # Verify error message propagation (Rich hard-wraps output at console
    # width, which can split this message mid-phrase on long tmp paths)
    normalized_output = " ".join(result.output.split())
    assert error_message in normalized_output, (
        f"Expected error message in output: {result.output}"
    )


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
    mocker: MockerFixture,
    cli_args: list[str],
    expected: dict[str, object],
) -> None:
    """Validates that CLI flags map to ExecutionContext arguments on RenderEngine."""
    mocker.patch("boilerplate.cli.commands.new.compute_composition")
    mock_render_engine = mocker.patch("boilerplate.cli.commands.new.RenderEngine")

    # Add explicit dirs/paths to keep environment-independent
    full_args = [
        *cli_args,
        str(temp_project_dir),  # positional destination argument
        "--templates-dir",
        str(fake_template_dir),
    ]
    typer_cli_runner.invoke(app, full_args)

    # Verify the render call with ExecutionContext containing expected parameters
    mock_render_engine.assert_called_once()
    render_call = mock_render_engine.return_value.render.call_args
    assert render_call is not None
    execution_ctx = render_call[0][1]  # Second argument is ExecutionContext
    assert execution_ctx.interactive is expected["interactive"]
    assert execution_ctx.overwrite is expected["overwrite"]


@pytest.mark.usefixtures("interactive_tty")
def test_new_handles_render_failure_behavior(
    typer_cli_runner: CliRunner,
    fake_template_dir: Path,
    temp_project_dir: Path,
    mocker: MockerFixture,
) -> None:
    """Tests that render failures are properly propagated to user."""
    # Mock RenderEngine to raise a RuntimeError
    mock_render_engine = mocker.patch("boilerplate.cli.commands.new.RenderEngine")
    mock_render_engine.return_value.render.side_effect = RuntimeError("copy failed")
    result = typer_cli_runner.invoke(
        app,
        [
            "new",
            "mytpl",
            str(temp_project_dir),
            "--templates-dir",
            str(fake_template_dir),
        ],
    )
    # Focus on behavior: error message propagation
    assert "copy failed" in result.output


@pytest.mark.usefixtures("interactive_tty")
def test_new_default_is_interactive(
    typer_cli_runner: CliRunner,
    fake_template_dir: Path,
    temp_project_dir: Path,
    mocker: MockerFixture,
) -> None:
    """Interactive mode is enabled by default and creates destination."""
    mocker.patch("boilerplate.cli.commands.new.compute_composition")
    mock_render_engine = mocker.patch("boilerplate.cli.commands.new.RenderEngine")

    typer_cli_runner.invoke(
        app,
        [
            "new",
            "mytpl",
            str(temp_project_dir),  # positional destination argument
            "--templates-dir",
            str(fake_template_dir),
        ],
    )

    # Verify interactive=True by default in ExecutionContext
    mock_render_engine.assert_called_once()
    render_call = mock_render_engine.return_value.render.call_args
    assert render_call is not None
    execution_ctx = render_call[0][1]  # Second argument is ExecutionContext
    assert execution_ctx.interactive is True


@pytest.mark.usefixtures("interactive_tty")
class TestCiModeAndNoTasks:
    """`--ci` and `--no-tasks` propagate into ExecutionContext as promised."""

    def test_ci_flag_sets_non_interactive_and_skip_tasks(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        temp_project_dir: Path,
        mocker: MockerFixture,
    ) -> None:
        """`boilerplate --ci new ...` honors the full four-flag implication."""
        ctx = _invoke_and_capture_execution_ctx(
            typer_cli_runner,
            fake_template_dir,
            temp_project_dir,
            mocker,
            ["--ci", "new", "project"],
        )
        assert ctx.interactive is False  # type: ignore[attr-defined]
        assert ctx.skip_tasks is True  # type: ignore[attr-defined]

    def test_no_tasks_flag_alone_sets_skip_tasks(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        temp_project_dir: Path,
        mocker: MockerFixture,
    ) -> None:
        """`--no-tasks` without `--ci` still propagates to ExecutionContext."""
        ctx = _invoke_and_capture_execution_ctx(
            typer_cli_runner,
            fake_template_dir,
            temp_project_dir,
            mocker,
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
        mocker: MockerFixture,
    ) -> None:
        """Without any flag, tasks run (skip_tasks=False on ExecutionContext)."""
        ctx = _invoke_and_capture_execution_ctx(
            typer_cli_runner,
            fake_template_dir,
            temp_project_dir,
            mocker,
            ["new", "project"],
        )
        assert ctx.skip_tasks is False  # type: ignore[attr-defined]

    def test_ci_env_var_alone_sets_non_interactive_and_skip_tasks(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        temp_project_dir: Path,
        mocker: MockerFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """BOILERPLATE_CI=1 with no flags matches --ci's full implication chain."""
        monkeypatch.setenv("BOILERPLATE_CI", "1")
        ctx = _invoke_and_capture_execution_ctx(
            typer_cli_runner,
            fake_template_dir,
            temp_project_dir,
            mocker,
            ["new", "project"],
        )
        assert ctx.interactive is False  # type: ignore[attr-defined]
        assert ctx.skip_tasks is True  # type: ignore[attr-defined]


class TestNonInteractiveEnvVar:
    """``BOILERPLATE_NON_INTERACTIVE`` joins ``--non-interactive`` with OR semantics."""

    def test_env_var_alone_behaves_like_flag(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        temp_project_dir: Path,
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
            mocker,
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
            mocker,
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
        mocker: MockerFixture,
        monkeypatch: pytest.MonkeyPatch,
        value: str,
    ) -> None:
        monkeypatch.setenv("BOILERPLATE_NON_INTERACTIVE", value)

        ctx = _invoke_and_capture_execution_ctx(
            typer_cli_runner,
            fake_template_dir,
            temp_project_dir,
            mocker,
            ["new", "project"],
        )
        assert ctx.interactive is True  # type: ignore[attr-defined]

    def test_flag_and_env_var_compose(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        temp_project_dir: Path,
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
            mocker,
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
        mocker: MockerFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Regression: generic CI=true does not switch input mode (see ADR-013)."""
        mocker.patch(
            "boilerplate.cli.commands.new._stdin_supports_prompts",
            return_value=False,
        )
        mock_render_engine = mocker.patch("boilerplate.cli.commands.new.RenderEngine")
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
        )

        assert result.exit_code == ExitCode.VALIDATION_ERROR
        assert "BP_INPUT_TTY_REQUIRED" in result.output
        mock_render_engine.return_value.render.assert_not_called()


@pytest.mark.usefixtures("interactive_tty")
class TestDataFlagsCliWiring:
    """`--data`/`--data-file` reach `ExecutionContext.context_data`."""

    def test_data_flag_populates_context_data(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        temp_project_dir: Path,
        mocker: MockerFixture,
    ) -> None:
        ctx = _invoke_and_capture_execution_ctx(
            typer_cli_runner,
            fake_template_dir,
            temp_project_dir,
            mocker,
            ["new", "project", "--data", "project_name=my-app"],
        )
        assert ctx.context_data == {"project_name": "my-app"}  # type: ignore[attr-defined]

    def test_repeated_data_flags_merge(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        temp_project_dir: Path,
        mocker: MockerFixture,
    ) -> None:
        ctx = _invoke_and_capture_execution_ctx(
            typer_cli_runner,
            fake_template_dir,
            temp_project_dir,
            mocker,
            ["new", "project", "--data", "a=1", "--data", "b=2"],
        )
        assert ctx.context_data == {"a": "1", "b": "2"}  # type: ignore[attr-defined]

    def test_data_file_flag_populates_context_data(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        temp_project_dir: Path,
        mocker: MockerFixture,
        tmp_path: Path,
    ) -> None:
        data_file = tmp_path / "answers.yml"
        data_file.write_text("project_name: from-file\n", encoding="utf-8")
        ctx = _invoke_and_capture_execution_ctx(
            typer_cli_runner,
            fake_template_dir,
            temp_project_dir,
            mocker,
            ["new", "project", "--data-file", str(data_file)],
        )
        assert ctx.context_data == {"project_name": "from-file"}  # type: ignore[attr-defined]

    def test_data_wins_over_data_file_on_collision(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        temp_project_dir: Path,
        mocker: MockerFixture,
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
            mocker,
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
        mocker: MockerFixture,
    ) -> None:
        ctx = _invoke_and_capture_execution_ctx(
            typer_cli_runner,
            fake_template_dir,
            temp_project_dir,
            mocker,
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
        mocker: MockerFixture,
    ) -> None:
        mock_render_engine = mocker.patch("boilerplate.cli.commands.new.RenderEngine")

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
        )

        assert result.exit_code == ExitCode.VALIDATION_ERROR
        assert "BP_INPUT_DATA_INVALID" in result.output
        mock_render_engine.return_value.render.assert_not_called()

    def test_missing_data_file_exits_validation_error(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        temp_project_dir: Path,
        tmp_path: Path,
        mocker: MockerFixture,
    ) -> None:
        mock_render_engine = mocker.patch("boilerplate.cli.commands.new.RenderEngine")
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
        )

        assert result.exit_code == ExitCode.VALIDATION_ERROR
        assert "BP_INPUT_DATA_INVALID" in result.output
        mock_render_engine.return_value.render.assert_not_called()

    def test_non_mapping_data_file_exits_validation_error(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        temp_project_dir: Path,
        tmp_path: Path,
        mocker: MockerFixture,
    ) -> None:
        mock_render_engine = mocker.patch("boilerplate.cli.commands.new.RenderEngine")
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
        )

        assert result.exit_code == ExitCode.VALIDATION_ERROR
        assert "BP_INPUT_DATA_INVALID" in result.output
        mock_render_engine.return_value.render.assert_not_called()

    def test_invalid_yaml_data_file_exits_validation_error(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        temp_project_dir: Path,
        tmp_path: Path,
        mocker: MockerFixture,
    ) -> None:
        mock_render_engine = mocker.patch("boilerplate.cli.commands.new.RenderEngine")
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
        )

        assert result.exit_code == ExitCode.VALIDATION_ERROR
        assert "BP_INPUT_DATA_INVALID" in result.output
        mock_render_engine.return_value.render.assert_not_called()

    def test_underscore_prefixed_data_key_exits_validation_error(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        temp_project_dir: Path,
        mocker: MockerFixture,
    ) -> None:
        mock_render_engine = mocker.patch("boilerplate.cli.commands.new.RenderEngine")

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
        )

        assert result.exit_code == ExitCode.VALIDATION_ERROR
        assert "BP_INPUT_DATA_INVALID" in result.output
        mock_render_engine.return_value.render.assert_not_called()

    def test_dry_run_with_malformed_data_entry_exits_validation_error(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        temp_project_dir: Path,
        mocker: MockerFixture,
    ) -> None:
        """Regression: --dry-run does not skip --data/--data-file validation."""
        mock_render_engine = mocker.patch("boilerplate.cli.commands.new.RenderEngine")

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
        )

        assert result.exit_code == ExitCode.VALIDATION_ERROR
        assert "BP_INPUT_DATA_INVALID" in result.output
        mock_render_engine.return_value.render.assert_not_called()

    def test_dry_run_with_missing_data_file_exits_validation_error(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        temp_project_dir: Path,
        tmp_path: Path,
        mocker: MockerFixture,
    ) -> None:
        """Regression: --dry-run does not skip --data/--data-file validation."""
        mock_render_engine = mocker.patch("boilerplate.cli.commands.new.RenderEngine")
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
        )

        assert result.exit_code == ExitCode.VALIDATION_ERROR
        assert "BP_INPUT_DATA_INVALID" in result.output
        mock_render_engine.return_value.render.assert_not_called()


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
        mocker: MockerFixture,
    ) -> None:
        mocker.patch(
            "boilerplate.cli.commands.new._stdin_supports_prompts",
            return_value=False,
        )
        mock_render_engine = mocker.patch("boilerplate.cli.commands.new.RenderEngine")

        result = typer_cli_runner.invoke(
            app,
            [
                "new",
                "mytpl",
                str(temp_project_dir),
                "--templates-dir",
                str(fake_template_dir),
            ],
        )

        assert result.exit_code == ExitCode.VALIDATION_ERROR
        assert "BP_INPUT_TTY_REQUIRED" in result.output
        assert "--non-interactive" in result.output
        mock_render_engine.return_value.render.assert_not_called()

    @pytest.mark.parametrize("flag", ["--non-interactive", "--yes"])
    def test_non_interactive_flags_bypass_guard(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        temp_project_dir: Path,
        mocker: MockerFixture,
        flag: str,
    ) -> None:
        mocker.patch(
            "boilerplate.cli.commands.new._stdin_supports_prompts",
            return_value=False,
        )
        mocker.patch("boilerplate.cli.commands.new.compute_composition")
        mock_render_engine = mocker.patch("boilerplate.cli.commands.new.RenderEngine")

        result = typer_cli_runner.invoke(
            app,
            [
                "new",
                "mytpl",
                str(temp_project_dir),
                flag,
                "--templates-dir",
                str(fake_template_dir),
            ],
        )

        assert result.exit_code == ExitCode.SUCCESS, result.output
        mock_render_engine.return_value.render.assert_called_once()

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
        mocker: MockerFixture,
    ) -> None:
        mocker.patch("boilerplate.cli.commands.new.compute_composition")
        mock_render_engine = mocker.patch("boilerplate.cli.commands.new.RenderEngine")

        result = typer_cli_runner.invoke(
            app,
            [
                "new",
                "mytpl",
                "--non-interactive",
                "--templates-dir",
                str(fake_template_dir),
            ],
        )

        assert result.exit_code == ExitCode.VALIDATION_ERROR, result.output
        assert "destination is required in non-interactive mode" in result.output
        assert "BP_INPUT_DEST_REQUIRED" in result.output
        mock_render_engine.return_value.render.assert_not_called()

    def test_ci_without_destination_exits_validation_error(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        mocker: MockerFixture,
    ) -> None:
        mocker.patch("boilerplate.cli.commands.new.compute_composition")
        mock_render_engine = mocker.patch("boilerplate.cli.commands.new.RenderEngine")

        result = typer_cli_runner.invoke(
            app, ["--ci", "new", "mytpl", "--templates-dir", str(fake_template_dir)]
        )

        assert result.exit_code == ExitCode.VALIDATION_ERROR, result.output
        mock_render_engine.return_value.render.assert_not_called()

    @pytest.mark.usefixtures("interactive_tty")
    def test_interactive_without_destination_prompts_for_it(
        self,
        typer_cli_runner: CliRunner,
        fake_template_dir: Path,
        temp_project_dir: Path,
        mocker: MockerFixture,
    ) -> None:
        mocker.patch("boilerplate.cli.commands.new.compute_composition")
        mock_render_engine = mocker.patch("boilerplate.cli.commands.new.RenderEngine")

        result = typer_cli_runner.invoke(
            app,
            ["new", "mytpl", "--templates-dir", str(fake_template_dir)],
            input=f"{temp_project_dir}\n",
        )

        assert result.exit_code == ExitCode.SUCCESS, result.output
        execution_ctx = mock_render_engine.return_value.render.call_args[0][1]
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
