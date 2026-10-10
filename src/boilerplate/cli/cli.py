"""Main application wiring for the Boilerplate CLI.

Bootstraps settings, logging, Runtime, and registers commands.
"""
# Spec: docs/design/05-cli-reference.md

import codecs
import sys
from collections.abc import Mapping, Sequence
from typing import Final, NoReturn

import typer
from typer.core import TyperGroup

import boilerplate
from boilerplate.cli import engine
from boilerplate.cli.commands import (
    compose,
    graph,
    new,
    templates,
    validate,
)
from boilerplate.cli.context import CliContext
from boilerplate.cli.display import ColorMode, Display
from boilerplate.cli.seams import Seams
from boilerplate.cli.utils import ensure_verbose_quiet_exclusive
from boilerplate.common.env import env_flag
from boilerplate.constants import ExitCode
from boilerplate.logging_config import configure_logging
from boilerplate.settings import Settings


def _reraise_as_validation_error(error: engine.UsageError) -> NoReturn:
    """Retag a click usage error with the taxonomy's exit code and re-raise.

    click defaults usage errors to exit 2, which docs/design/02-data-models.md
    §Exit Codes reserves for ``CONFIG_ERROR``; bad command-line input is
    ``VALIDATION_ERROR``. Only the code changes, so click still renders the
    message and usage hint itself.

    Args:
        error: The usage error on its way out of the CLI.

    Raises:
        engine.UsageError: Always — the same instance, exit code corrected.
    """
    error.exit_code = ExitCode.VALIDATION_ERROR
    raise error


# Where the root context keeps, for the banner, the arguments it parsed and the
# encoding stdout had before the root callback forces UTF-8 onto it.
_ARGS_KEY: Final = "boilerplate.args"
_ENCODING_KEY: Final = "boilerplate.stdout_encoding"


def _color_mode(value: object) -> ColorMode:
    """Return the ``--color`` mode that an unconverted option value names.

    Args:
        value: What Click's parser read for ``--color``, if anything.

    Returns:
        The mode named, or ``auto`` when none or an invalid one is given.
    """
    if isinstance(value, str) and value in ColorMode:
        return ColorMode(value)
    return ColorMode.AUTO


class BoilerplateGroup(TyperGroup):
    """Typer group that pins usage-error exit codes and opens help with the banner.

    ``make_context`` covers root-level parsing and ``invoke`` covers subcommand
    parsing plus errors raised inside command bodies, which is every path the
    engine routes through ``Command.main``. Suggesting a close command on a
    typo is Typer's own behavior and needs nothing here.
    """

    def parse_args(self, ctx: engine.Context, args: list[str]) -> list[str]:
        """Parse the root arguments, keeping what the banner needs.

        That is the arguments themselves and stdout's encoding as the
        terminal set it, before the root callback reconfigures it to UTF-8.
        A command name after ``--`` that looks like an option, as in
        ``-q -- --help``, is parsed a second time on its own; the banner keeps
        the first parse's arguments, which hold the root's own options.
        """
        ctx.meta.setdefault(_ARGS_KEY, tuple(args))
        ctx.meta.setdefault(_ENCODING_KEY, getattr(sys.stdout, "encoding", None))
        return super().parse_args(ctx, args)

    def format_help(self, ctx: engine.Context, formatter: engine.HelpFormatter) -> None:
        """Print the top-level help, opening with the banner (05 §Banner).

        Help formatted from a context that never parsed command-line
        arguments, such as one built directly to render the help text, prints
        without the banner: there are no arguments to read the root's options
        from.
        """
        args = ctx.meta.get(_ARGS_KEY)
        if args is not None:
            options = self._root_options(ctx, args)
            Display(
                color=_color_mode(options.get("color")),
                quiet=bool(options.get("quiet")),
            ).banner(terminal_encoding=ctx.meta.get(_ENCODING_KEY))
        super().format_help(ctx, formatter)

    def _root_options(
        self, ctx: engine.Context, args: Sequence[str]
    ) -> Mapping[str, object]:
        """Return the root's own options as Click's parser reads them from ``args``.

        ``--help`` is eager, so the help it prints is formatted before Click
        processes the root's other options; the banner reads them with the
        same parser instead, unconverted. The parser stops at the subcommand's
        name, splits clustered short flags such as ``-qh``, and keeps the last
        value of an option given twice.
        """
        options, _, _ = self.make_parser(ctx).parse_args(args=list(args))
        return options

    def make_context(
        self,
        info_name: str | None,
        args: list[str],
        parent: engine.Context | None = None,
        **extra: object,
    ) -> engine.Context:
        """Build the root context, pinning parse-error exit codes."""
        try:
            return super().make_context(info_name, args, parent, **extra)
        except engine.UsageError as e:
            _reraise_as_validation_error(e)

    def invoke(self, ctx: engine.Context) -> object:
        """Dispatch to the subcommand, pinning its usage-error exit codes."""
        try:
            return super().invoke(ctx)
        except engine.UsageError as e:
            _reraise_as_validation_error(e)


app = typer.Typer(
    name="boilerplate",
    cls=BoilerplateGroup,
    help=(
        "Composable project scaffolder with template layering on top of Copier."
        "\n\nGet started:\n\n"
        "    boilerplate list\n"
        "    boilerplate new project my-app\n"
        "    boilerplate new streamlit my-dashboard"
    ),
    rich_markup_mode="rich",
    pretty_exceptions_enable=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)


COLOR_OPTION = typer.Option(
    ColorMode.AUTO,
    "--color",
    help="Color output.",
)


def _reconfigure_stdio_encoding() -> None:
    """Reconfigures stdout/stderr to UTF-8 so CLI glyphs survive legacy codepages.

    Windows consoles default to codepages (cp437, cp1252) that raise
    ``UnicodeEncodeError`` on non-ASCII output such as the composition-sequence
    arrow. ``errors="replace"`` degrades gracefully instead of crashing.
    ``reconfigure`` mutates the stream in place, so handlers that already
    hold a reference to it (e.g. the JSON log handler in
    ``configure_logging``, per docs/design/07-operational-quality.md
    §Structured Logging) see the change; substituting characters cannot
    corrupt the surrounding JSON structure. Streams without ``reconfigure``
    (piped/captured) are left alone.
    """
    for stream in (sys.stdout, sys.stderr):
        encoding = getattr(stream, "encoding", None)
        reconfigure = getattr(stream, "reconfigure", None)
        if (
            encoding
            and callable(reconfigure)
            and codecs.lookup(encoding).name != "utf-8"
        ):
            reconfigure(encoding="utf-8", errors="replace")


def _print_help_and_exit(ctx: typer.Context) -> None:
    """Print top-level help and exit successfully.

    Kept separate for clarity and easier testing of the help path.
    """
    typer.echo(ctx.get_help())
    raise typer.Exit(code=ExitCode.SUCCESS)


def _version_callback(value: bool) -> None:
    """Print version and exit when --version is passed."""
    if value:
        typer.echo(f"boilerplate {boilerplate.__version__}")
        raise typer.Exit()


def _bootstrap_runtime(
    verbose: bool,
    quiet: bool,
    color: ColorMode,
    ci_mode: bool,
    seams: Seams,
) -> CliContext:
    """Create and configure the CLI runtime.

    - Instantiates Display (user-facing boundary)
    - Loads Settings with concise error handling
    - Configures logging once, with clear precedence:
      CLI --verbose takes priority; otherwise use settings.debug.
    - Threads the injected renderer from `seams` into the CliContext.

    Note: configure_logging is treated as idempotent; the implementation
    defers to logging.basicConfig, which is a no-op when handlers exist.
    """
    display = Display(color=color, quiet=quiet)
    try:
        settings = Settings()
    except Exception as e:  # CLI boundary: keep user message concise
        display.error(f"Error: {e}")
        raise typer.Exit(code=ExitCode.CONFIG_ERROR) from e

    # Precedence: CLI flag wins; otherwise fall back to config
    configure_logging(debug=verbose or settings.debug, ci=ci_mode)

    return CliContext(
        settings=settings,
        display=display,
        renderer=seams.renderer,
        verbose=verbose,
        quiet=quiet,
        ci_mode=ci_mode,
    )


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable debug logging.",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Hide the banner and progress, success, and hint messages.",
    ),
    color: ColorMode = COLOR_OPTION,
    ci: bool = typer.Option(
        False,
        "--ci",
        help="Never prompt and log JSON to stderr. Implies --non-interactive on new.",
    ),
    _version: bool = typer.Option(
        False,
        "--version",
        help="Show version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """Initialize runtime context and global logging."""
    _reconfigure_stdio_encoding()

    # If no subcommand is invoked (None or empty string), show help and
    # exit without bootstrapping.
    if not ctx.invoked_subcommand:
        _print_help_and_exit(ctx)

    # Tool-scoped opt-in; the generic CI var is deliberately never read
    # (ADR-013 rationale).
    ci = ci or env_flag("BOILERPLATE_CI")

    # The --ci implication (--non-interactive) is honored by subcommands via
    # CliContext.ci_mode. Output volume is not part of it: a pipeline that
    # wants debug logs passes --ci --verbose.
    ensure_verbose_quiet_exclusive(verbose, quiet)

    # Pick up an injected Seams (e.g. a test's recording renderer) if one was
    # passed as `obj` to the runner; otherwise fall back to the real one.
    seams = ctx.ensure_object(Seams)

    # Bootstrap runtime once for subcommands, attach to Typer context.
    ctx.obj = _bootstrap_runtime(verbose, quiet, color, ci_mode=ci, seams=seams)


# Register commands with grouping for help output
app.command("list", rich_help_panel="Use a template")(templates.list_templates)
app.command("new", rich_help_panel="Use a template")(new.new)
app.command("graph", rich_help_panel="Author a template")(graph.graph)
app.command("compose", rich_help_panel="Author a template")(compose.compose)
app.command("validate", rich_help_panel="Author a template")(validate.validate)
