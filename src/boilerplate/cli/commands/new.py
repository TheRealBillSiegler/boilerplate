"""Renders a template to a destination directory (scaffold generation).

Lean logging only:
- Debug: non-obvious decisions (explicit version, custom templates dir, overwrite)
- No performance timing, thresholds, or complexity heuristics
"""

import ctypes
import json
import sys
from logging import getLogger
from pathlib import Path
from typing import Any, TextIO

import typer
import yaml
from typer import Context

from boilerplate.cli.common import TEMPLATES_DIR_OPTION
from boilerplate.cli.utils import cli_error_handler, compute_composition
from boilerplate.common.env import env_flag
from boilerplate.common.exceptions import (
    InteractiveModeRequiresTtyError,
    InvalidDataError,
)
from boilerplate.common.yaml_loading import load_yaml
from boilerplate.composition.rendering.engine import RenderEngine
from boilerplate.composition.rendering.models.execution_context import ExecutionContext
from boilerplate.settings.profile import load_profile
from boilerplate.types import TemplateSpecifier

DESTINATION_ARG = typer.Argument(
    Path(),
    help="Destination directory for the new project (defaults to current directory).",
)
DATA_OPTION = typer.Option(
    None,
    "--data",
    help=(
        "Forced answer for one question, as key=value (repeatable). Never "
        "prompted for; satisfies non-interactive's required-answer check."
    ),
)
DATA_FILE_OPTION = typer.Option(
    None,
    "--data-file",
    help="YAML file mapping question name to forced answer (read as UTF-8).",
)

_logger = getLogger(__name__)


def _apply_ci_mode_and_yes(
    *,
    ci_mode: bool,
    non_interactive: bool,
    yes: bool,
    no_tasks: bool,
) -> tuple[bool, bool]:
    """Resolves final ``(non_interactive, no_tasks)`` from raw flag values.

    ``--ci`` implies ``--non-interactive --yes --no-tasks``. ``--yes``
    implies ``--non-interactive``. Subcommand flags compose with OR
    semantics: if any source turns a behavior on, it stays on.

    Args:
        ci_mode: Whether global ``--ci`` was passed.
        non_interactive: Whether subcommand ``--non-interactive`` was passed.
        yes: Whether subcommand ``--yes`` was passed.
        no_tasks: Whether subcommand ``--no-tasks`` was passed.

    Returns:
        A tuple ``(effective_non_interactive, effective_no_tasks)``.
    """
    effective_non_interactive = non_interactive or yes or ci_mode
    effective_no_tasks = no_tasks or ci_mode
    return effective_non_interactive, effective_no_tasks


def _stdin_supports_prompts() -> bool:
    """Returns True when stdin can host interactive prompts (a real TTY).

    A module-level seam so tests can simulate either environment: CI,
    piped execution, and captured test runs all leave stdin without a TTY.
    """
    stdin: TextIO | None = sys.stdin  # None under pythonw / detached processes
    try:
        if stdin is None or not stdin.isatty():
            return False
    except (ValueError, OSError):
        return False  # a closed or invalid stdin can never host prompts
    return _stdin_is_real_console()


_STD_INPUT_HANDLE = -10


def _stdin_is_real_console() -> bool:
    """Rejects character devices that ``isatty()`` misreports as terminals.

    On Windows ``isatty()`` returns True for any character device — including
    ``NUL`` — so ``< NUL`` redirection passes the isatty check even though the
    console input API can never deliver keystrokes and the prompt would hang
    forever. ``GetConsoleMode`` succeeds only on genuine console input
    handles, which is the same discriminator the prompt layer relies on.
    """
    if sys.platform != "win32":
        return True
    kernel32 = ctypes.windll.kernel32
    kernel32.GetStdHandle.restype = ctypes.c_void_p
    handle = kernel32.GetStdHandle(_STD_INPUT_HANDLE)
    if not handle:
        return False
    mode = ctypes.c_uint32()
    return bool(kernel32.GetConsoleMode(ctypes.c_void_p(handle), ctypes.byref(mode)))


def _require_tty_for_interactive(*, non_interactive: bool, dry_run: bool) -> None:
    """Fails closed when an interactive render could never receive answers.

    In a non-TTY environment Copier's prompt layer (questionary /
    prompt_toolkit) may retry-loop on EOF instead of raising, growing
    memory without bound — so the render must be refused before Copier
    starts.

    Args:
        non_interactive: Effective non-interactive flag after --ci/--yes
            composition; when True the guard is skipped.
        dry_run: Whether --dry-run was passed; dry runs never prompt, so
            they stay legal when piped.

    Raises:
        InteractiveModeRequiresTtyError: Interactive mode is requested but
            stdin is not a TTY.
    """
    if dry_run or non_interactive or _stdin_supports_prompts():
        return
    raise InteractiveModeRequiresTtyError(
        "Interactive mode requires a terminal, but stdin is not a TTY "
        "(CI, piped input, or a session without a console)."
    )


def _validate_data_key(key: object, source: str) -> None:
    """Rejects a forced-answer key shared by ``--data`` and ``--data-file``.

    Args:
        key: Candidate key as parsed from ``source``.
        source: Human-readable description of where the key came from, for
            the error message (e.g. ``"--data-file 'answers.yml'"``).

    Raises:
        InvalidDataError: ``key`` is not a string, is empty or
            whitespace-only, or starts with an underscore (Copier's
            reserved-directive namespace).
    """
    if not isinstance(key, str):
        raise InvalidDataError(
            f"{source} has key {key!r}, which is not a string. YAML parses "
            "unquoted on/off/yes/no and bare numbers as booleans or "
            "numbers; quote the key in the YAML source to keep it a string."
        )
    if not key.strip():
        raise InvalidDataError(f"{source} has an empty key.")
    if key.startswith("_"):
        raise InvalidDataError(
            f"{source} has key '{key}': names starting with an underscore "
            "are reserved by Copier for its own directives."
        )


def _parse_data_entries(entries: list[str] | None) -> dict[str, Any]:
    """Parses repeatable ``--data key=value`` entries into a forced-answers dict.

    Args:
        entries: Raw ``key=value`` strings in CLI order; ``None`` when
            ``--data`` was not passed.

    Returns:
        Mapping of question name to forced answer. A key repeated across
        entries takes its last value (later flags win).

    Raises:
        InvalidDataError: An entry has no ``=`` separator, an empty key, or
            a leading-underscore key (reserved by Copier).
    """
    parsed: dict[str, Any] = {}
    for entry in entries or []:
        key, sep, value = entry.partition("=")
        if not sep or not key.strip():
            raise InvalidDataError(
                f"Malformed --data entry '{entry}': expected key=value."
            )
        _validate_data_key(key, f"--data entry '{entry}'")
        parsed[key] = value
    return parsed


def _load_data_file(path: Path | None) -> dict[str, Any]:
    """Loads forced answers from a ``--data-file`` YAML mapping.

    Args:
        path: Path passed to ``--data-file``; ``None`` when the option was
            not supplied.

    Returns:
        The parsed mapping; empty when ``path`` is ``None`` or the file
        parses to an empty document.

    Raises:
        InvalidDataError: The file cannot be read (including as UTF-8), its
            YAML is malformed, it does not parse to a mapping, or one of its
            keys is not a string, is empty, or starts with an underscore.
    """
    if path is None:
        return {}
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise InvalidDataError(f"Cannot read --data-file '{path}': {exc}") from exc
    try:
        data = load_yaml(text)
    except yaml.YAMLError as exc:
        raise InvalidDataError(
            f"--data-file '{path}' is not valid YAML: {exc}"
        ) from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise InvalidDataError(
            f"--data-file '{path}' must contain a YAML mapping of question "
            "name to answer."
        )
    for key in data:
        _validate_data_key(key, f"--data-file '{path}'")
    return data


def _resolve_data(data: list[str] | None, data_file: Path | None) -> dict[str, Any]:
    """Merges ``--data-file`` and ``--data`` into one forced-answers dict.

    Precedence on key collision: ``--data`` wins over ``--data-file``. Both
    ride Copier's ``data`` channel (forced answers), distinct from the
    profile's overridable ``user_defaults`` channel.

    Args:
        data: Raw ``--data key=value`` entries.
        data_file: Path from ``--data-file``, or ``None``.

    Returns:
        Merged forced-answers dict for ``ExecutionContext.context_data``.

    Raises:
        InvalidDataError: Either source fails to parse.
    """
    merged = _load_data_file(data_file)
    merged.update(_parse_data_entries(data))
    return merged


def _resolve_profile(
    spec: TemplateSpecifier | None, template_spec: str
) -> dict[str, Any]:
    """Returns the profile's default answers for the invoked root template.

    Args:
        spec: Parsed template specifier when the argument carried a version,
            else ``None``.
        template_spec: The raw template argument, used when ``spec`` is ``None``.

    Returns:
        The merged profile answers for the template; empty when none apply.
    """
    root_template_name = spec.name if spec else template_spec
    profile = load_profile(root_template_name)
    if profile:
        _logger.debug("Applying %d profile default(s) from profile.toml", len(profile))
    return profile


@cli_error_handler
def new(
    ctx: Context,
    template_spec: str = typer.Argument(
        ..., help="Template specifier (name or name@version)."
    ),
    destination: Path = DESTINATION_ARG,
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite destination if it exists.",
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        "-n",
        help="Run in non-interactive mode using default values for all questions.",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Accept all defaults without prompting (implies --non-interactive).",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be created without writing files.",
    ),
    no_tasks: bool = typer.Option(
        False,
        "--no-tasks",
        help="Skip post-generation task execution.",
    ),
    data: list[str] | None = DATA_OPTION,
    data_file: Path | None = DATA_FILE_OPTION,
    format: str | None = typer.Option(None, "--format", help="Output format: json."),
    templates_dir: Path | None = TEMPLATES_DIR_OPTION,
) -> None:
    """Renders the specified template and version into a destination directory."""
    cli_context = ctx.obj
    display = cli_context.display
    settings = cli_context.settings

    # Tool-scoped opt-in; the generic CI var is deliberately never read
    # (ADR-013 rationale).
    non_interactive, no_tasks = _apply_ci_mode_and_yes(
        ci_mode=cli_context.ci_mode,
        non_interactive=non_interactive or env_flag("BOILERPLATE_NON_INTERACTIVE"),
        yes=yes,
        no_tasks=no_tasks,
    )
    _require_tty_for_interactive(non_interactive=non_interactive, dry_run=dry_run)

    # Resolve destination directory (no log - obvious)
    dest_dir = destination

    if templates_dir:
        _logger.debug("Using user-specified template root: %s", templates_dir)

    # Execute template rendering
    # Parse template specifier; if no version provided, use latest
    spec = (
        TemplateSpecifier.from_string(template_spec) if "@" in template_spec else None
    )
    template_ref = spec.name if spec else template_spec
    if spec and spec.version:
        template_ref = f"{spec.name}@{spec.version}"
        _logger.debug("Using explicit template version: %s", template_ref)
    elif "@" not in template_spec:
        _logger.debug("No version specified; resolving latest for '%s'", template_spec)

    render_engine = RenderEngine()

    json_mode = format == "json"

    if not json_mode:
        display.info("Resolving dependencies and composing layers...")
    composition = compute_composition(template_ref, templates_dir, settings)

    # Validate --data/--data-file before any dry-run output: a malformed
    # flag must fail even when nothing would be rendered.
    context_data = _resolve_data(data, data_file)

    if dry_run:
        layer_names = " → ".join(composition.sequence)
        if json_mode:
            display.write(
                json.dumps(
                    {
                        "dry_run": True,
                        "template": template_spec,
                        "layers": composition.sequence,
                        "destination": str(dest_dir),
                    }
                )
            )
        else:
            display.info(f"Dry run: would render {layer_names} to {dest_dir}")
        _logger.debug("Dry run completed for template '%s'", template_spec)
        return

    # Build execution context. The profile (profile.toml) pre-fills the
    # questionnaire as overridable defaults: an interactive answer overrides
    # them, and --yes takes them as-is. It rides Copier's user_defaults
    # channel, not the forced-answer (data) channel. --data/--data-file are
    # forced answers: taken as-is, never prompted for, and win over the
    # profile on a key collision (--data over --data-file over profile).
    execution_ctx = ExecutionContext(
        destination=dest_dir,
        context_data=context_data,
        profile=_resolve_profile(spec, template_spec),
        overwrite=force,
        interactive=not non_interactive,
        skip_tasks=no_tasks,
    )

    # Step 3: Apply templates
    if not json_mode:
        display.info(f"Rendering to {dest_dir}...")
    template_info = render_engine.render(composition, execution_ctx)
    if destination.exists() and force:
        _logger.debug("Overwrite applied due to --force: %s", destination)

    if json_mode:
        display.write(
            json.dumps(
                {
                    "template": template_info.name,
                    "destination": str(dest_dir),
                    "layers": composition.sequence,
                }
            )
        )
    else:
        # Post-creation guidance
        display.success(f"Template '{template_info.name}' rendered to '{dest_dir}'.")
        display.write("")
        display.info("Next steps:")
        display.write(f"  cd {dest_dir}")
        display.write("  uv sync")
    _logger.debug("New command completed: template '%s'", template_info.name)


__all__ = ["new"]
