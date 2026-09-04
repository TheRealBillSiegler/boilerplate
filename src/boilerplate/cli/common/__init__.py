"""Typer option definitions shared by more than one Boilerplate command."""

import typer

TEMPLATES_DIR_OPTION = typer.Option(
    None,
    "--templates-dir",
    help="Path to your Boilerplate templates directory.",
)

OUTPUT_OPTION = typer.Option(None, "--output", "-o", help="Output file or directory.")

QUIET_OPTION = typer.Option(False, "--quiet", help="Suppress stdout output.")

__all__ = ["OUTPUT_OPTION", "QUIET_OPTION", "TEMPLATES_DIR_OPTION"]
