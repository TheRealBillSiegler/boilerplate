"""Unit tests for boilerplate.cli.utils."""

from collections.abc import Callable
from pathlib import Path

import pytest
import typer
from pytest_mock import MockerFixture
from typer.core import TyperCommand

from boilerplate.cli.context import CliContext
from boilerplate.cli.display import ColorMode, Display
from boilerplate.cli.engine import UsageError
from boilerplate.cli.utils import (
    build_template_catalog,
    build_template_table_data,
    cli_error_handler,
    render_template_table,
    resolve_templates_directories,
)
from boilerplate.common.exceptions import (
    ActionRequiredError,
    AddAncestorsMissingError,
    AddAncestorVersionError,
    AnswersFileIncompleteError,
    BoilerplateError,
    DestinationNotEmptyError,
    DirectoryValidationError,
    InvalidTemplateSpecifierError,
    InvalidVersionError,
    LayerAlreadyAddedError,
    MetadataValidationError,
    MissingRequiredAnswersError,
    NonInteractiveRequiresForceError,
    ProjectNotManagedError,
    RecordedAnswerRejectedError,
    TemplateNotFoundError,
    UpdateCheckoutChangedError,
    UpdateConflictPausedError,
    UpdateDowngradeError,
    UpdateInterruptedError,
    UpdateLayerDriftError,
    UpdatePathObstructedError,
    UpdateProjectNotReadyError,
    UpdateSubmodulesUnsupportedError,
    UpdateTargetMismatchError,
    UpdateUnknownLayerError,
    UserCancelledError,
)
from boilerplate.composition.graph.exceptions import (
    DependencyCycleError,
    DependencyNotFoundError,
)
from boilerplate.composition.merging.exceptions import MergeConflictError
from boilerplate.composition.rendering.renderer import Renderer
from boilerplate.constants import ExitCode
from boilerplate.models.template_info import TemplateInfo
from boilerplate.settings import Settings


@pytest.fixture
def template_infos(template_factory: Callable[..., TemplateInfo]) -> list[TemplateInfo]:
    # Use the template_factory fixture from conftest.py
    return [
        template_factory("foo", "1.0.0", description="desc"),
        template_factory("bar", "1.0.0", description="desc"),
    ]


@pytest.mark.parametrize(
    (
        "show_path",
        "expected_headers",
        "expected_len",
        "expected_first",
        "expected_second",
    ),
    [
        (True, ["Name", "Version", "Description", "Path"], 4, "foo", "bar"),
        (False, ["Name", "Version", "Description"], 3, "foo", "bar"),
    ],
    ids=["with-path-column", "without-path-column"],
)
def test_build_template_table_data_param(
    template_infos: list[TemplateInfo],
    show_path: bool,
    expected_headers: list[str],
    expected_len: int,
    expected_first: str,
    expected_second: str,
) -> None:
    headers, rows = build_template_table_data(template_infos, show_path=show_path)
    assert headers == expected_headers
    assert all(len(row) == expected_len for row in rows)
    assert rows[0][0] == expected_first
    assert rows[1][0] == expected_second


def test_render_template_table_calls_display(
    template_infos: list[TemplateInfo],
) -> None:
    captured = {}

    class FakeDisplay:
        def table(
            self, headers: list[str], rows: list[tuple[str, ...]], **_kwargs
        ) -> None:
            captured["headers"] = headers
            captured["rows"] = rows

    render_template_table([template_infos[0]], FakeDisplay(), show_path=True)  # type: ignore[arg-type]
    assert captured["headers"] == ["Name", "Version", "Description", "Path"]
    assert captured["rows"][0][0] == "foo"


def test_resolve_templates_directories_prepends_flag_dir(tmp_path: Path) -> None:
    """--templates-dir is prepended to search path, not a replacement.

    Per docs/design/05-cli-reference.md §Global Options, the flag's directory is
    added to the catalog build before the configured directories, so bundled and
    configured templates remain available.
    """
    settings = Settings()
    result = resolve_templates_directories(tmp_path, settings)
    assert result == [tmp_path, *settings.template_dirs]
    assert settings.default_templates_dir in result


def test_resolve_templates_directories_falls_back_to_settings(tmp_path: Path) -> None:
    """Tests resolving templates directories falls back to settings.template_dirs."""
    dir1 = tmp_path / "dir1"
    dir2 = tmp_path / "dir2"
    dir1.mkdir()
    dir2.mkdir()

    settings = Settings()
    settings.default_templates_dir = dir1
    settings.extra_template_dirs = [dir2]

    result = resolve_templates_directories(None, settings)
    assert result == [dir1, dir2]


def test_build_template_catalog_rejects_a_missing_directory(tmp_path: Path) -> None:
    """A templates directory that does not exist is a configuration error."""
    settings = Settings()
    missing = tmp_path / "nonexistent"

    with pytest.raises(DirectoryValidationError) as exc_info:
        build_template_catalog(missing, settings)

    assert str(missing) in str(exc_info.value)


def test_build_template_catalog_reports_actual_permission_denied(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    """A real PermissionError is reported as permission denied."""
    settings = Settings()
    settings.extra_template_dirs = [tmp_path]

    mocker.patch(
        "boilerplate.cli.utils.DirectoryTemplateRepository",
        side_effect=PermissionError("Access is denied"),
    )

    with pytest.raises(DirectoryValidationError) as exc_info:
        build_template_catalog(None, settings)

    assert "Permission denied" in str(exc_info.value)


def test_build_template_catalog_preserves_non_permission_os_error_text(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    """A non-permission OSError is not rewritten as a fabricated 'Permission denied'.

    Regression test: build_template_catalog used to catch (PermissionError,
    OSError) as one clause and always report "Permission denied", discarding
    the real OSError reason (e.g. disk I/O errors, path-too-long).
    """
    settings = Settings()
    settings.extra_template_dirs = [tmp_path]

    mocker.patch(
        "boilerplate.cli.utils.DirectoryTemplateRepository",
        side_effect=OSError("Disk I/O error"),
    )

    with pytest.raises(DirectoryValidationError) as exc_info:
        build_template_catalog(None, settings)

    message = str(exc_info.value)
    assert "Disk I/O error" in message
    assert "Permission denied" not in message


class TestCliErrorHandler:
    """cli_error_handler routes BoilerplateError subclasses to documented exit codes.

    The mapping is specified in docs/design/02-data-models.md §Error Hierarchy.
    Each documented exception class must map to its declared exit code; the
    catch-all path for unrecognized BoilerplateError subclasses must remain
    `FAILURE` (1).
    """

    @staticmethod
    def _decorate_raiser(exc: BaseException) -> Callable[[], None]:
        """Wrap a function that raises ``exc`` with cli_error_handler."""

        @cli_error_handler
        def _raise() -> None:
            raise exc

        return _raise

    @pytest.mark.parametrize(
        ("exception", "expected_code"),
        [
            # Exit 1 (FAILURE)
            (TemplateNotFoundError("missing template"), ExitCode.FAILURE),
            (DependencyNotFoundError("dep missing"), ExitCode.FAILURE),
            # Exit 2 (CONFIG_ERROR)
            (DirectoryValidationError("bad dir"), ExitCode.CONFIG_ERROR),
            # Exit 3 (VALIDATION_ERROR)
            (InvalidVersionError("not pep440"), ExitCode.VALIDATION_ERROR),
            (
                InvalidTemplateSpecifierError("bad specifier"),
                ExitCode.VALIDATION_ERROR,
            ),
            (MetadataValidationError("bad metadata"), ExitCode.VALIDATION_ERROR),
            (
                DestinationNotEmptyError("destination not empty"),
                ExitCode.VALIDATION_ERROR,
            ),
            (
                NonInteractiveRequiresForceError("needs --force"),
                ExitCode.VALIDATION_ERROR,
            ),
            (
                MissingRequiredAnswersError("answers required"),
                ExitCode.VALIDATION_ERROR,
            ),
            (
                RecordedAnswerRejectedError("recorded answer rejected"),
                ExitCode.VALIDATION_ERROR,
            ),
            (AnswersFileIncompleteError("incomplete"), ExitCode.VALIDATION_ERROR),
            (UpdateLayerDriftError("drift"), ExitCode.VALIDATION_ERROR),
            (UpdateTargetMismatchError("mismatch"), ExitCode.VALIDATION_ERROR),
            (UpdateDowngradeError("downgrade"), ExitCode.VALIDATION_ERROR),
            (UpdateSubmodulesUnsupportedError("submodules"), ExitCode.VALIDATION_ERROR),
            (UpdateCheckoutChangedError("changed"), ExitCode.VALIDATION_ERROR),
            (UpdatePathObstructedError("obstructed"), ExitCode.VALIDATION_ERROR),
            (UpdateInterruptedError("interrupted"), ExitCode.VALIDATION_ERROR),
            (UpdateProjectNotReadyError("dirty"), ExitCode.VALIDATION_ERROR),
            (UpdateUnknownLayerError("no such layer"), ExitCode.VALIDATION_ERROR),
            (ProjectNotManagedError("unmanaged"), ExitCode.VALIDATION_ERROR),
            (LayerAlreadyAddedError("present"), ExitCode.VALIDATION_ERROR),
            (AddAncestorsMissingError("missing"), ExitCode.VALIDATION_ERROR),
            (AddAncestorVersionError("too old"), ExitCode.VALIDATION_ERROR),
            # Exit 4 (ACTION_REQUIRED) — recoverable workflow pause
            (
                ActionRequiredError("resolve conflicts, then re-run"),
                ExitCode.ACTION_REQUIRED,
            ),
            (UpdateConflictPausedError("paused"), ExitCode.ACTION_REQUIRED),
            # Exit 130 (USER_CANCELLED)
            (UserCancelledError(), ExitCode.USER_CANCELLED),
        ],
        ids=[
            "template-not-found",
            "dependency-not-found",
            "directory-validation",
            "invalid-version",
            "invalid-template-specifier",
            "metadata-validation",
            "destination-not-empty",
            "non-interactive-requires-force",
            "missing-required-answers",
            "recorded-answer-rejected",
            "answers-file-incomplete",
            "layer-drift",
            "target-mismatch",
            "downgrade",
            "submodules-unsupported",
            "checkout-changed",
            "path-obstructed",
            "interrupted",
            "project-not-ready",
            "unknown-layer",
            "project-not-managed",
            "layer-already-added",
            "ancestors-missing",
            "ancestor-version",
            "action-required",
            "conflict-paused",
            "user-cancelled",
        ],
    )
    def test_documented_exception_mapping(
        self, exception: BoilerplateError, expected_code: ExitCode
    ) -> None:
        """Each documented exception routes to its spec-mandated exit code."""
        wrapped = self._decorate_raiser(exception)

        with pytest.raises(typer.Exit) as exc_info:
            wrapped()

        assert exc_info.value.exit_code == expected_code

    @pytest.mark.parametrize(
        "exception",
        [
            DependencyCycleError("cycle detected"),
            MergeConflictError("conflict"),
            BoilerplateError("plain base error"),
        ],
        ids=["dependency-cycle", "merge-conflict", "base-error"],
    )
    def test_unspecified_boilerplate_error_falls_back_to_failure(
        self, exception: BoilerplateError
    ) -> None:
        """Subclasses not explicitly mapped hit the FAILURE catch-all."""
        wrapped = self._decorate_raiser(exception)

        with pytest.raises(typer.Exit) as exc_info:
            wrapped()

        assert exc_info.value.exit_code == ExitCode.FAILURE

    def test_user_cancelled_error_prints_single_concise_line(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Ctrl+C at a prompt produces one line, no internals, nonzero exit.

        Regression test for a Ctrl+C dumping Copier's internal AnswersMap/
        Question/Template repr instead of exiting cleanly.
        """
        wrapped = self._decorate_raiser(UserCancelledError())

        with pytest.raises(typer.Exit) as exc_info:
            wrapped()

        assert exc_info.value.exit_code == ExitCode.USER_CANCELLED
        captured = capsys.readouterr()
        assert captured.err.strip() == "Error: Aborted.   [BP_RENDER_USER_CANCELLED]"
        assert captured.err.count("\n") <= 1
        assert "AnswersMap" not in captured.err
        assert "Question(" not in captured.err

    def test_non_boilerplate_exception_falls_back_to_failure(self) -> None:
        """Arbitrary exceptions outside the hierarchy exit with FAILURE."""
        wrapped = self._decorate_raiser(RuntimeError("boom"))

        with pytest.raises(typer.Exit) as exc_info:
            wrapped()

        assert exc_info.value.exit_code == ExitCode.FAILURE

    def test_typer_exit_passes_through_unchanged(self) -> None:
        """typer.Exit propagates with its original code, untouched."""
        wrapped = self._decorate_raiser(typer.Exit(code=42))

        with pytest.raises(typer.Exit) as exc_info:
            wrapped()

        assert exc_info.value.exit_code == 42

    @pytest.mark.parametrize(
        "exception",
        [
            typer.BadParameter("bad arg"),
            UsageError("plain usage error"),
        ],
        ids=["bad-parameter", "plain-usage-error"],
    )
    def test_usage_errors_reach_the_app_boundary_intact(
        self, exception: UsageError
    ) -> None:
        """Usage errors escape the handler so the app group can render and code them.

        Swallowing them here would render the message twice and flatten the exit
        code to FAILURE; the taxonomy mapping lives in the app group instead
        (docs/design/02-data-models.md §Exit Codes).
        """
        wrapped = self._decorate_raiser(exception)

        with pytest.raises(UsageError) as exc_info:
            wrapped()

        assert exc_info.value is exception

    def test_error_renders_through_context_display_without_a_ctx_argument(
        self,
        capsys: pytest.CaptureFixture[str],
        renderer: Renderer,
        mocker: MockerFixture,
    ) -> None:
        """The Display comes from the active Click context, not from the arguments.

        Regression: the handler scanned ``*args`` for an object exposing
        ``.obj.display``, so a decorated helper invoked with keyword arguments
        only bypassed the command's Display entirely and fell through to the
        bare ``typer.echo`` fallback. Both paths print the same text (the
        ``Fix:`` line no longer depends on ``quiet``, see
        ``test_remediation_line_survives_quiet``), so a spy on ``typer.echo``
        is what proves the context path ran instead of the fallback.
        """
        echo_spy = mocker.patch("typer.echo")
        ctx = typer.Context(TyperCommand("stub"))
        ctx.obj = CliContext(
            settings=Settings(),
            display=Display(color=ColorMode.NEVER, quiet=False),
            renderer=renderer,
        )
        wrapped = self._decorate_raiser(
            DestinationNotEmptyError("destination /tmp/out is not empty")
        )

        with ctx, pytest.raises(typer.Exit):
            wrapped()

        echo_spy.assert_not_called()
        captured = capsys.readouterr()
        assert "Error: destination /tmp/out is not empty" in captured.err

    def test_validation_error_propagates_error_code_and_remediation(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """VALIDATION_ERROR clauses surface error_code and remediation."""
        wrapped = self._decorate_raiser(
            DestinationNotEmptyError("destination /tmp/out is not empty")
        )

        with pytest.raises(typer.Exit):
            wrapped()

        captured = capsys.readouterr()
        # The Error: line carries the registered code as a bracketed suffix,
        # per docs/design/07-operational-quality.md §Error Message Format.
        assert "Error: destination /tmp/out is not empty" in captured.err
        assert "[BP_RENDER_DEST_NOT_EMPTY]" in captured.err
        assert "Use --force to overwrite." in captured.err

    def test_remediation_line_uses_the_fix_label(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The remediation line reads 'Fix:', matching design 07's own label.

        Regression: the boundary shipped 'Hint:' where design
        07-operational-quality.md §Error Message Format specifies 'Fix:'.
        """
        wrapped = self._decorate_raiser(
            DestinationNotEmptyError("destination /tmp/out is not empty")
        )

        with pytest.raises(typer.Exit):
            wrapped()

        captured = capsys.readouterr()
        assert "Fix: Use --force to overwrite." in captured.err
        assert "Hint:" not in captured.err

    def test_remediation_line_goes_to_stderr_through_display(
        self, capsys: pytest.CaptureFixture[str], renderer: Renderer
    ) -> None:
        """The Fix: line prints to stderr, never stdout, through a real Display.

        Regression: the boundary printed the Fix: line via ``Display.info``,
        which writes to stdout. docs/design/05-cli-reference.md §Output
        Display requires errors, and their remediation, on stderr only.
        """
        ctx = typer.Context(TyperCommand("stub"))
        ctx.obj = CliContext(
            settings=Settings(),
            display=Display(color=ColorMode.NEVER, quiet=False),
            renderer=renderer,
        )
        wrapped = self._decorate_raiser(
            DestinationNotEmptyError("destination /tmp/out is not empty")
        )

        with ctx, pytest.raises(typer.Exit):
            wrapped()

        captured = capsys.readouterr()
        assert "Fix: Use --force to overwrite." in captured.err
        assert "Fix:" not in captured.out

    def test_remediation_line_survives_quiet(
        self, capsys: pytest.CaptureFixture[str], renderer: Renderer
    ) -> None:
        """--quiet leaves the Fix: line in place; it is part of the error.

        Regression: ``Display.info`` suppresses its message under ``quiet``,
        but docs/design/05-cli-reference.md §Quiet Mode permits only error
        messages (to stderr) under ``--quiet``, and the Fix: line is a
        component of the error per design 07 §Error Message Format, not
        suppressible progress output.
        """
        ctx = typer.Context(TyperCommand("stub"))
        ctx.obj = CliContext(
            settings=Settings(),
            display=Display(color=ColorMode.NEVER, quiet=True),
            renderer=renderer,
        )
        wrapped = self._decorate_raiser(
            DestinationNotEmptyError("destination /tmp/out is not empty")
        )

        with ctx, pytest.raises(typer.Exit):
            wrapped()

        captured = capsys.readouterr()
        assert "Fix: Use --force to overwrite." in captured.err
        assert captured.out == ""
