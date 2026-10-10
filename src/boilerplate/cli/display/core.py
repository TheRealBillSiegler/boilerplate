"""Core display primitives for styled CLI output (Rich boundary).

This module defines the Display class and related theme configuration.
"""

import os
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from rich import box
from rich.console import Console
from rich.table import Table
from rich.theme import Theme

from boilerplate.cli.display.banner import build_banner
from boilerplate.cli.display.color_mode import ColorMode
from boilerplate.cli.display.terminal_probe import read_terminal_facts
from boilerplate.common.env import env_flag

ColorSystem = Literal["auto", "standard", "256", "truecolor", "windows"]

DEFAULT_THEME = Theme(
    {
        "info": "cyan",
        "success": "green",
        "warning": "yellow",
        "error": "bold red",
    },
)


def _resolve_color_system(color: ColorMode) -> ColorSystem | None:
    """Resolve the Rich color_system from the --color mode.

    Args:
        color: The mode selected with ``--color``.

    Returns:
        Rich color_system value, or None for auto-detection.
    """
    if color is ColorMode.ALWAYS:
        return "truecolor"
    return None  # auto-detect


class Display:
    """Provides styled printing helpers for CLI output.

    The message methods (info, success, warning, error, error_detail) style the
    whole line and print its text as given, without parsing Rich markup: messages
    carry names and paths the user typed, and a ``[`` in them is literal text.
    """

    theme: Theme
    console: Console
    error_console: Console
    quiet: bool

    def __init__(
        self,
        theme: Theme | None = None,
        *,
        color: ColorMode = ColorMode.AUTO,
        quiet: bool = False,
    ) -> None:
        """Initialize the display with a custom or default theme.

        Args:
            theme: Optional Rich theme override.
            color: The mode selected with ``--color``.
            quiet: If True, suppress info/success output (errors still shown).
        """
        if theme is not None:
            merged_styles = dict(DEFAULT_THEME.styles)
            merged_styles.update(theme.styles)
            self.theme = Theme(merged_styles)
        else:
            self.theme = DEFAULT_THEME

        accessible = env_flag("BOILERPLATE_ACCESSIBLE")
        no_color = "NO_COLOR" in os.environ
        force_no_color = color is ColorMode.NEVER or accessible or no_color

        color_system: str | None = _resolve_color_system(color)
        if color is ColorMode.ALWAYS:
            # An explicit --color wins over NO_COLOR, which Rich would
            # otherwise read from the environment on its own.
            self.console = Console(
                theme=self.theme,
                color_system=color_system,
                force_terminal=True,
                no_color=False,
            )
            self.error_console = Console(
                theme=self.theme,
                stderr=True,
                color_system=color_system,
                force_terminal=True,
                no_color=False,
            )
        elif force_no_color:
            # Rich's no_color keeps bold and dim; color_system=None renders
            # every style as bare text, which is what never and NO_COLOR
            # require (docs/design/05-cli-reference.md, Terminal Accessibility).
            self.console = Console(theme=self.theme, no_color=True, color_system=None)
            self.error_console = Console(
                theme=self.theme, stderr=True, no_color=True, color_system=None
            )
        else:
            self.console = Console(theme=self.theme)
            self.error_console = Console(theme=self.theme, stderr=True)

        self.quiet = quiet

    # Pager removed from CLI.

    def info(self, message: str) -> None:
        """Print an informational message using the 'info' style.

        Suppressed when ``quiet`` is set.

        Args:
            message: Text to print to stdout.
        """
        if self.quiet:
            return
        self.console.print(message, style="info", markup=False)

    def success(self, message: str) -> None:
        """Print a success message using the 'success' style.

        Suppressed when ``quiet`` is set.

        Args:
            message: Text to print to stdout.
        """
        if self.quiet:
            return
        self.console.print(message, style="success", markup=False)

    def banner(self, *, terminal_encoding: str | None = None) -> None:
        """Print the banner, after a blank line, when the terminal can show it.

        The layout, and every case where none prints, follow
        docs/design/05-cli-reference.md §Banner. Suppressed when ``quiet`` is
        set. When no banner prints, neither does its blank line. Nothing
        follows the banner: the top-level help it opens starts with a blank
        line of its own.

        Args:
            terminal_encoding: The encoding stdout had before the CLI forced
                UTF-8 onto it, which decides whether the banner may draw
                braille; ``None`` takes the console's own encoding.
        """
        if self.quiet:
            return
        facts = read_terminal_facts(self.console, encoding=terminal_encoding)
        art = build_banner(facts)
        if art is None:
            return
        self.console.print()
        self.console.print(art, no_wrap=True, overflow="ignore", crop=False)

    def warning(self, message: str) -> None:
        """Print a warning message using the 'warning' style."""
        self.error_console.print(message, style="warning", markup=False)

    def error(self, message: str) -> None:
        """Print an error message using the 'error' style."""
        self.error_console.print(message, style="error", markup=False)

    def error_detail(self, message: str) -> None:
        """Print an indented continuation line following an ``Error:`` line.

        Used for an error's indented reason and ``Fix:`` lines: they are components
        of the error itself (docs/design/07-operational-quality.md §Error
        Message Format), not separate progress output, so unlike ``info``
        this always goes to stderr and always prints, ``quiet`` included.

        Args:
            message: The indented continuation text to print.
        """
        self.error_console.print(message, style="info", markup=False)

    def write(self, content: str, *, end: str = "\n") -> None:
        """Low-level print that preserves exact endings.

        This wraps Rich Console.print to keep CLI output behind Display while
        allowing callers to control trailing newlines (e.g., for YAML dumps).
        Markup parsing, highlighting, and width-based wrapping are disabled
        so machine-readable payloads (JSON/YAML) reach stdout byte-exact,
        regardless of terminal width, color mode, or TTY status.
        """
        self.console.print(
            content, end=end, markup=False, highlight=False, soft_wrap=True
        )

    def write_line(self, content: str = "") -> None:
        """Print a single line (convenience over write)."""
        self.write(content)

    def table(
        self,
        headers: Sequence[str],
        rows: Sequence[tuple[str, ...]],
        *,
        expand: bool = False,
        wrap_last_column: bool = False,
        path_column_index: int | None = None,
    ) -> None:
        """Render a table with styled headers and optional rows."""
        tbl = Table(header_style="info", box=box.SIMPLE_HEAVY, expand=expand)

        # Add columns with appropriate settings
        for i, header in enumerate(headers):
            is_last = i == len(headers) - 1
            is_path_column = path_column_index is not None and i == path_column_index

            if is_path_column:
                # Path column gets special treatment - no truncation, smart wrapping
                tbl.add_column(
                    header,
                    overflow="fold",
                    no_wrap=False,
                    min_width=40,
                    ratio=3,  # Give paths more space
                )
            elif is_last and wrap_last_column:
                # Last column with wrapping enabled
                tbl.add_column(
                    header, overflow="fold", no_wrap=False, min_width=20, max_width=60
                )
            elif header in ["#", "Version"]:
                # Numeric columns should be narrow and not wrap
                tbl.add_column(header, overflow="ellipsis", no_wrap=True, max_width=12)
            else:
                # Standard columns with ellipsis for non-path content
                tbl.add_column(header, overflow="ellipsis", no_wrap=True)

        # Zebra striping: alternate row styles
        row_styles = ["none", "dim"]
        for idx, row_data in enumerate(rows):
            processed_row = row_data
            if path_column_index is not None and path_column_index < len(row_data):
                modified_row = list(row_data)
                path = modified_row[path_column_index]
                try:
                    file_url = Path(path).as_uri()
                except ValueError:
                    pass  # relative path: no file URI; leave the cell plain
                else:
                    modified_row[path_column_index] = f"[link={file_url}]{path}[/link]"
                processed_row = tuple(modified_row)

            tbl.add_row(*processed_row, style=row_styles[idx % len(row_styles)])
        self.console.print(tbl)
