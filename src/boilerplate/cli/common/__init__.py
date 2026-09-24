"""Typer option definitions shared by more than one Boilerplate command."""

import typer

TEMPLATES_DIR_OPTION = typer.Option(
    None,
    "--templates-dir",
    help="Extra directory to search for templates, in addition to the bundled ones.",
)

QUIET_OPTION = typer.Option(
    False,
    "--quiet",
    help="Print nothing to stdout; pair with --output to only write files.",
)

__all__ = ["QUIET_OPTION", "TEMPLATES_DIR_OPTION"]
