"""Main application wiring for the Boilerplate CLI.

Bootstraps settings, logging, Runtime, and registers commands.
"""
# Spec: docs/design/05-cli-reference.md

import codecs
import difflib
import sys
from typing import NoReturn

import click
import typer
from typer import Context
from typer.core import TyperGroup

import boilerplate
from boilerplate.cli.commands import (
    compose,
    graph,
    new,
    templates,
    validate,
    version,
)
from boilerplate.cli.context import CliContext
from boilerplate.cli.display.core import Display
from boilerplate.cli.utils import ensure_verbose_quiet_exclusive
from boilerplate.common.env import env_flag
from boilerplate.constants import ExitCode
from boilerplate.logging_config import configure_logging
from boilerplate.settings import Settings


def _reraise_as_validation_error(error: click.UsageError) -> NoReturn:
    """Retags a click usage error with the taxonomy's exit code and re-raise.

    click defaults usage errors to exit 2, which docs/design/02-data-models.md
    §Exit Codes reserves for ``CONFIG_ERROR``; bad command-line input is
    ``VALIDATION_ERROR``. Only the code changes, so click still renders the
    message and usage hint itself.

    Args:
        error: The usage error on its way out of the CLI.

    Raises:
        click.UsageError: Always — the same instance, exit code corrected.
    """
    error.exit_code = ExitCode.VALIDATION_ERROR
    raise error


class BoilerplateGroup(TyperGroup):
    """Typer group that suggests similar commands on typos.

    Also the single place usage-error exit codes are pinned: ``make_context``
    covers root-level parsing and ``invoke`` covers subcommand parsing plus
    errors raised inside command bodies, which is every path click routes
    through ``BaseCommand.main``.
    """

    def make_context(
        self,
        info_name: str | None,
        args: list[str],
        parent: click.Context | None = None,
        **extra: object,
    ) -> click.Context:
        """Builds the root context, pinning parse-error exit codes."""
        try:
            return super().make_context(info_name, args, parent, **extra)
        except click.UsageError as e:
            _reraise_as_validation_error(e)

    def invoke(self, ctx: click.Context) -> object:
        """Dispatches to the subcommand, pinning its usage-error exit codes."""
        try:
            return super().invoke(ctx)
        except click.UsageError as e:
            _reraise_as_validation_error(e)

    def resolve_command(
        self, ctx: click.Context, args: list[str]
    ) -> tuple[str | None, click.Command | None, list[str]]:
        """Resolves command, suggesting close matches on failure."""
        try:
            return super().resolve_command(ctx, args)
        except click.UsageError as e:
            if args:
                cmd_name = args[0]
                matches = difflib.get_close_matches(
                    cmd_name, self.list_commands(ctx), n=1, cutoff=0.6
                )
                if matches:
                    msg = f"No such command '{cmd_name}'. Did you mean '{matches[0]}'?"
                    raise click.UsageError(msg) from e
            raise


app = typer.Typer(
    name="boilerplate",
    cls=BoilerplateGroup,
    help=(
        "Composable project scaffolder with template layering on top of Copier."
        "\n\nGet started:"
        "\n  boilerplate list               # browse templates"
        "\n  boilerplate new project my-app # scaffold a project"
    ),
    rich_markup_mode="rich",
    pretty_exceptions_enable=True,
    context_settings={"help_option_names": ["-h", "--help"]},
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


def _print_help_and_exit(ctx: Context) -> None:
    """Prints top-level help and exit successfully.

    Kept separate for clarity and easier testing of the help path.
    """
    typer.echo(ctx.get_help())
    raise typer.Exit(code=ExitCode.SUCCESS)


def _version_callback(value: bool) -> None:
    """Prints version and exit when --version is passed."""
    if value:
        typer.echo(f"boilerplate {boilerplate.__version__}")
        raise typer.Exit()


def _bootstrap_runtime(
    verbose: bool,
    quiet: bool,
    color: str | None,
    ci_mode: bool,
) -> CliContext:
    """Creates and configures the CLI runtime.

    - Instantiates Display (user-facing boundary)
    - Loads Settings with concise error handling
    - Configures logging once, with clear precedence:
      CLI --verbose takes priority; otherwise use settings.debug.

    Note: configure_logging is treated as idempotent; the implementation
    defers to logging.basicConfig, which is a no-op when handlers exist.
    """
    display = Display(color=color, quiet=quiet)
    try:
        settings = Settings()
    except Exception as e:  # CLI boundary: keep user message concise
        display.error(str(e))
        raise typer.Exit(code=ExitCode.CONFIG_ERROR) from e

    # Precedence: CLI flag wins; otherwise fall back to config
    configure_logging(debug=verbose or settings.debug, ci=ci_mode)

    return CliContext(
        settings=settings,
        display=display,
        verbose=verbose,
        quiet=quiet,
        ci_mode=ci_mode,
    )


@app.callback(invoke_without_command=True)
def main(
    ctx: Context,
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
        help="Suppress informational output.",
    ),
    color: str = typer.Option(
        "auto",
        "--color",
        help="Color output: auto, always, or never.",
    ),
    ci: bool = typer.Option(
        False,
        "--ci",
        help="CI mode: implies --quiet --non-interactive --yes --no-tasks.",
    ),
    _version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """Initializes runtime context and global logging."""
    _reconfigure_stdio_encoding()

    # If no subcommand is invoked (None or empty string), show help and
    # exit without bootstrapping.
    if not ctx.invoked_subcommand:
        _print_help_and_exit(ctx)

    # Tool-scoped opt-in; the generic CI var is deliberately never read
    # (ADR-013 rationale).
    ci = ci or env_flag("BOILERPLATE_CI")

    # --ci implies --quiet; the remaining implications (--non-interactive,
    # --yes, --no-tasks) are honored by subcommands via CliContext.ci_mode.
    if ci:
        quiet = True

    ensure_verbose_quiet_exclusive(verbose, quiet)

    # Bootstrap runtime once for subcommands, attach to Typer context.
    ctx.obj = _bootstrap_runtime(verbose, quiet, color, ci_mode=ci)


# Register commands with grouping for help output
app.command("new", rich_help_panel="Project commands")(new.new)
app.command("list", rich_help_panel="Template commands")(templates.list_templates)
app.command("graph", rich_help_panel="Template commands")(graph.graph)
app.command("compose", rich_help_panel="Template commands")(compose.compose)
app.command("validate", rich_help_panel="Template commands")(validate.validate)
app.command("version", rich_help_panel="System commands")(version.version)
