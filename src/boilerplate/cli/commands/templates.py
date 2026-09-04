"""Command to list available Boilerplate templates."""

import json
from logging import getLogger
from pathlib import Path

import typer
from typer import Context

from boilerplate.cli.common import TEMPLATES_DIR_OPTION
from boilerplate.cli.utils import (
    build_template_catalog,
    cli_error_handler,
    render_template_table,
)
from boilerplate.constants import ExitCode

_logger = getLogger(__name__)

FORMAT_OPTION = typer.Option(None, "--format", help="Output format: json.")


@cli_error_handler
def list_templates(
    ctx: Context,
    templates_dir: Path = TEMPLATES_DIR_OPTION,
    format: str | None = FORMAT_OPTION,
) -> None:
    """Lists all templates found in the registry."""
    cli_context = ctx.obj
    display = cli_context.display
    settings = cli_context.settings

    registry = build_template_catalog(templates_dir, settings)
    template_infos = registry.list_all()

    if not template_infos:
        if format == "json":
            display.write(json.dumps({"templates": [], "error": "No templates found."}))
            raise typer.Exit(code=ExitCode.FAILURE)
        display.error("No templates found.")
        raise typer.Exit(code=ExitCode.FAILURE)

    if format == "json":
        data = [
            {
                "name": t.name,
                "version": str(t.meta.version),
                "description": t.meta.description,
                "path": str(t.location),
            }
            for t in template_infos
        ]
        display.write(json.dumps({"templates": data}))
    else:
        render_template_table(template_infos, display, show_path=cli_context.verbose)
    _logger.debug("Templates command completed: %d templates", len(template_infos))


__all__ = ["list_templates"]
