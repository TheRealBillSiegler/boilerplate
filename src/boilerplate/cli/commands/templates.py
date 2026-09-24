"""Command to list available Boilerplate templates."""

import json
from enum import StrEnum
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


class ListFormat(StrEnum):
    """Output formats for the template listing."""

    TABLE = "table"
    JSON = "json"
    WIDE = "wide"


FORMAT_OPTION = typer.Option(
    ListFormat.TABLE, "--format", help="Output format. wide adds each template's path."
)


@cli_error_handler
def list_templates(
    ctx: Context,
    templates_dir: Path = TEMPLATES_DIR_OPTION,
    format: ListFormat = FORMAT_OPTION,
) -> None:
    """List the templates you can create a project from."""
    cli_context = ctx.obj
    display = cli_context.display
    settings = cli_context.settings

    registry = build_template_catalog(templates_dir, settings)
    template_infos = registry.list_all()

    if not template_infos:
        if format is ListFormat.JSON:
            display.write(json.dumps({"templates": [], "error": "No templates found."}))
            raise typer.Exit(code=ExitCode.FAILURE)
        display.error("No templates found.")
        raise typer.Exit(code=ExitCode.FAILURE)

    if format is ListFormat.JSON:
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
        render_template_table(
            template_infos, display, show_path=format is ListFormat.WIDE
        )
    _logger.debug("Templates command completed: %d templates", len(template_infos))


__all__ = ["list_templates"]
