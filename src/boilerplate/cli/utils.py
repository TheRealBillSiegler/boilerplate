"""Shared CLI utilities for Boilerplate CLI commands."""

from collections.abc import Callable, Sequence
from functools import wraps
from logging import getLogger
from pathlib import Path
from typing import NoReturn

import click
import typer

from boilerplate.catalog import TemplateCatalog
from boilerplate.cli.display.core import Display
from boilerplate.cli.validators import validate_directory
from boilerplate.common.exceptions import (
    ActionRequiredError,
    BoilerplateError,
    DestinationNotEmptyError,
    DirectoryValidationError,
    InteractiveModeRequiresTtyError,
    InvalidDataError,
    InvalidTemplateSpecifierError,
    InvalidVersionError,
    MetadataValidationError,
    MissingRequiredAnswersError,
    NonInteractiveRequiresForceError,
    TemplateNotFoundError,
    UserCancelledError,
)
from boilerplate.composition import Composer
from boilerplate.composition.graph.exceptions import DependencyNotFoundError
from boilerplate.composition.models import Composition
from boilerplate.composition.resolution import Resolver
from boilerplate.constants import ExitCode
from boilerplate.models.template_info import TemplateInfo
from boilerplate.repository import DirectoryTemplateRepository
from boilerplate.settings import Settings

_logger = getLogger(__name__)


def _current_display() -> Display | None:
    """Returns the Display carried by the active Click context, if any.

    Commands always run inside a Click context whose object holds the
    Display. Unit tests call decorated helpers with no context at all, so the
    absence of one is a supported case, not an error.
    """
    ctx = click.get_current_context(silent=True)
    display = getattr(ctx.obj, "display", None) if ctx is not None else None
    return display if isinstance(display, Display) else None


def _display_error_and_exit(
    message: str,
    exit_code: ExitCode,
    *,
    error_code: str | None = None,
    remediation: str | None = None,
) -> NoReturn:
    """Displays error message with optional error code and remediation, then exit.

    The ``Error:`` line carries the stable ``BP_*`` code as a bracketed
    suffix, per docs/design/07-operational-quality.md §Error Message Format.
    """
    display = _current_display()
    suffix = f"   [{error_code}]" if error_code else ""
    if display:
        display.error(f"Error: {message}{suffix}")
        if remediation:
            display.info(f"  Hint: {remediation}")
    else:
        typer.echo(f"Error: {message}{suffix}", err=True)
        if remediation:
            typer.echo(f"  Hint: {remediation}", err=True)
    raise typer.Exit(code=exit_code)


def ensure_verbose_quiet_exclusive(verbose: bool, quiet: bool) -> None:
    """Rejects the mutually exclusive ``--verbose``/``--quiet`` combination.

    Single owner of the exclusivity contract: the root callback checks the
    global flags, and commands that accept a subcommand-position ``--quiet``
    re-check after merging it with the global value.

    Args:
        verbose: The effective verbose flag.
        quiet: The effective quiet flag.

    Raises:
        typer.Exit: With ``ExitCode.VALIDATION_ERROR`` when both are set.
    """
    if verbose and quiet:
        typer.echo("Error: --verbose and --quiet are mutually exclusive.", err=True)
        raise typer.Exit(code=ExitCode.VALIDATION_ERROR)


def cli_error_handler[**P, T](func: Callable[P, T]) -> Callable[P, T]:
    """Decorator to handle common CLI exceptions and convert to exit codes.

    This eliminates the need for scattered try/catch patterns across
    commands. Automatically handles BoilerplateError hierarchy and displays
    user-friendly messages.
    """

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return func(*args, **kwargs)
        except (typer.Exit, click.UsageError):
            # typer.Exit already carries its code; usage errors are rendered and
            # exit-coded by the app group (cli.py), not here.
            raise
        except (TemplateNotFoundError, DependencyNotFoundError) as e:
            _display_error_and_exit(
                str(e),
                ExitCode.FAILURE,
                error_code=getattr(e, "error_code", None),
                remediation=getattr(e, "remediation", None),
            )
        except DirectoryValidationError as e:
            _display_error_and_exit(
                str(e),
                ExitCode.CONFIG_ERROR,
                error_code=e.error_code,
                remediation=e.remediation,
            )
        except (
            InteractiveModeRequiresTtyError,
            InvalidDataError,
            InvalidVersionError,
            InvalidTemplateSpecifierError,
            MetadataValidationError,
            DestinationNotEmptyError,
            NonInteractiveRequiresForceError,
            MissingRequiredAnswersError,
        ) as e:
            _display_error_and_exit(
                str(e),
                ExitCode.VALIDATION_ERROR,
                error_code=e.error_code,
                remediation=e.remediation,
            )
        except ActionRequiredError as e:
            _display_error_and_exit(
                str(e),
                ExitCode.ACTION_REQUIRED,
                error_code=e.error_code,
                remediation=e.remediation,
            )
        except UserCancelledError as e:
            _display_error_and_exit(
                str(e),
                ExitCode.USER_CANCELLED,
                error_code=e.error_code,
                remediation=e.remediation,
            )
        except BoilerplateError as e:
            _display_error_and_exit(
                str(e),
                ExitCode.FAILURE,
                error_code=e.error_code,
                remediation=e.remediation,
            )
        except Exception as e:
            _display_error_and_exit(str(e), ExitCode.FAILURE)

    return wrapper


def build_template_catalog(
    templates_dir: Path | None,
    settings: Settings,
) -> TemplateCatalog:
    """Creates a TemplateCatalog from the configured template directories.

    Emits no UI messages and never exits the process: validation failures
    raise BoilerplateError and unexpected exceptions propagate, so commands
    map them to exit codes and user-facing messages themselves.

    Args:
        templates_dir: Directory from ``--templates-dir``, if given.
        settings: Settings supplying the configured directories.

    Returns:
        Catalog of every template discovered.

    Raises:
        DirectoryValidationError: A template directory is unreadable.
    """
    directories = resolve_templates_directories(templates_dir, settings)
    validated_dirs: list[Path] = [validate_directory(d) for d in directories]

    registry = TemplateCatalog()
    total_templates_processed = 0

    for directory in validated_dirs:
        try:
            repository = DirectoryTemplateRepository(directory)
            templates = repository.load_templates()
            for template in templates:
                registry.register(template)
                total_templates_processed += 1
        except PermissionError as e:
            raise DirectoryValidationError(
                f"Permission denied accessing directory: {directory}"
            ) from e
        except OSError as e:
            raise DirectoryValidationError(
                f"Error accessing directory {directory}: {e}"
            ) from e

    _logger.debug(
        "Template catalog created with %d unique templates from %d processed.",
        len(registry),
        total_templates_processed,
    )
    return registry


def compute_composition(
    template_ref: str,
    templates_dir: Path | None,
    settings: Settings,
    *,
    include_states: bool = False,
    include_deltas: bool = False,
) -> Composition:
    """Runs the catalog -> resolve -> compose pipeline for a template reference.

    Single owner of that pipeline for every command that needs a composition.
    Raises rather than exiting, so the caller's ``cli_error_handler`` maps the
    failure to an exit code.

    Args:
        template_ref: Template reference, ``name`` or ``name@version``.
        templates_dir: Directory from ``--templates-dir``, if given.
        settings: Settings supplying the configured directories.
        include_states: Capture each layer's post-merge state.
        include_deltas: Capture each layer's delta.

    Returns:
        The composed artifact for the resolved dependency graph.

    Raises:
        BoilerplateError: The catalog, the reference, or the merge is invalid.
    """
    registry = build_template_catalog(templates_dir, settings)
    resolution = Resolver().resolve(template_ref, registry)
    return Composer().compose(
        resolution,
        include_states=include_states,
        include_deltas=include_deltas,
    )


def resolve_templates_directories(
    templates_dir: Path | None,
    settings: Settings,
) -> list[Path]:
    """Returns the templates directories to search, priority-ordered.

    ``templates_dir`` (from ``--templates-dir``) is prepended to the
    configured ``settings.template_dirs`` rather than replacing them, so
    bundled and configured templates remain available for ``extends``
    resolution. See docs/design/05-cli-reference.md §Global Options
    (`--templates-dir`).
    """
    if templates_dir:
        return [templates_dir, *settings.template_dirs]
    return settings.template_dirs


def build_template_table_data(
    template_infos: Sequence[TemplateInfo],
    show_path: bool,
) -> tuple[list[str], Sequence[tuple[str, ...]]]:
    """Builds headers and rows for a template table."""
    if show_path:
        headers = ["Name", "Version", "Description", "Path"]
        rows = [
            (
                info.name,
                str(info.meta.version),
                info.meta.description,
                str(info.location),
            )
            for info in template_infos
        ]
    else:
        headers = ["Name", "Version", "Description"]
        rows = [
            (info.name, str(info.meta.version), info.meta.description)
            for info in template_infos
        ]
    return headers, rows


def render_template_table(
    template_infos: Sequence[TemplateInfo],
    display: Display,
    show_path: bool,
) -> None:
    """Renders a table of template infos using the display object."""
    headers, rows = build_template_table_data(template_infos, show_path)
    # When showing paths, make the path column (last column) clickable
    path_column_index = len(headers) - 1 if show_path else None
    display.table(
        headers,
        rows,
        expand=show_path,
        wrap_last_column=show_path,
        path_column_index=path_column_index,
    )
