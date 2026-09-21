"""Command to display the current version of the Boilerplate CLI."""

import json
from logging import getLogger

import typer
from typer import Context

import boilerplate
from boilerplate.cli.types import TextFormat
from boilerplate.cli.utils import cli_error_handler

_logger = getLogger(__name__)

FORMAT_OPTION = typer.Option(TextFormat.TEXT, "--format", help="Output format.")


@cli_error_handler
def version(
    ctx: Context,
    format: TextFormat = FORMAT_OPTION,
) -> None:
    """Show the installed CLI version."""
    cli_context = ctx.obj
    d = cli_context.display

    if format is TextFormat.JSON:
        d.write(json.dumps({"name": "boilerplate", "version": boilerplate.__version__}))
    else:
        d.write(f"boilerplate {boilerplate.__version__}")
    _logger.debug("Version command completed")
    raise typer.Exit()


__all__ = ["version"]
