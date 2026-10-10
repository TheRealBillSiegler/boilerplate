"""Read what the banner needs to know about the terminal.

The probes here ask the operating system and the environment, never the
terminal itself: an escape-sequence query needs raw mode and a timeout, and
Windows Terminal answers it with a fixed virtual cell
(docs/design/05-cli-reference.md §Banner).
"""
# Spec: docs/design/05-cli-reference.md §Banner

import codecs
import ctypes
import os
import struct
import sys
from typing import IO, Final

from rich.console import Console

from boilerplate.cli.display.terminal_facts import TerminalFacts
from boilerplate.common.env import env_flag

if sys.platform != "win32":
    import fcntl
    import termios

_DUMB_TERMS: Final = frozenset({"dumb", "unknown"})
# The Linux text console: its fonts carry no braille.
_LINUX_CONSOLE: Final = "linux"
# SystemParametersInfo action that reports whether a screen reader is running.
_SPI_GETSCREENREADER: Final = 0x0046


def read_terminal_facts(
    console: Console, *, encoding: str | None = None
) -> TerminalFacts:
    """Read the facts the banner decides on, for the console it prints to.

    Args:
        console: The console the banner would print to.
        encoding: The encoding stdout had before the CLI forced UTF-8 onto
            it; ``None`` takes the console's own encoding as the terminal's.

    Returns:
        The terminal's facts.
    """
    stream = console.file
    term = os.environ.get("TERM", "")
    size = console.size
    utf8 = _is_utf8(encoding or console.encoding)
    return TerminalFacts(
        interactive=_is_terminal(stream) and term not in _DUMB_TERMS,
        columns=size.width,
        lines=size.height,
        braille=utf8 and term != _LINUX_CONSOLE,
        ascii_only=console.no_color,
        accessible=env_flag("BOILERPLATE_ACCESSIBLE") or _screen_reader_running(),
        opted_out=env_flag("BOILERPLATE_NO_BANNER"),
        cell_shape=_reported_cell_shape(stream),
    )


def cell_shape(rows: int, columns: int, x_pixels: int, y_pixels: int) -> float | None:
    """Return a terminal's cell height divided by its cell width.

    Args:
        rows: The window's height, in rows.
        columns: The window's width, in columns.
        x_pixels: The window's width, in pixels.
        y_pixels: The window's height, in pixels.

    Returns:
        The cell shape, or ``None`` when the report is implausible: under 2
        pixels per column or 4 per row, the plausibility test timg applies.

    Examples:
        >>> cell_shape(rows=24, columns=80, x_pixels=640, y_pixels=432)
        2.25
        >>> cell_shape(rows=24, columns=80, x_pixels=0, y_pixels=0) is None
        True
    """
    if not rows or not columns or x_pixels < 2 * columns or y_pixels < 4 * rows:
        return None
    return (y_pixels / rows) / (x_pixels / columns)


def _is_terminal(stream: IO[str]) -> bool:
    """Return True when ``stream`` is a terminal.

    A stream without ``isatty``, as some embedding hosts install, is none.
    """
    isatty = getattr(stream, "isatty", None)
    try:
        return bool(isatty and isatty())
    except (ValueError, OSError):
        return False  # a closed or detached stream is no terminal


def _is_utf8(encoding: str) -> bool:
    """Return True when ``encoding`` names UTF-8."""
    try:
        return codecs.lookup(encoding).name == "utf-8"
    except LookupError:
        return False


def _reported_cell_shape(stream: IO[str]) -> float | None:
    """Return the cell shape the terminal reports for its window, if any.

    Reads ``TIOCGWINSZ`` on POSIX. Windows has no pixel report for a console
    window, so the shape is unknown there.
    """
    if sys.platform == "win32":
        return None
    try:
        report = fcntl.ioctl(stream.fileno(), termios.TIOCGWINSZ, bytes(8))
    except (AttributeError, ValueError, OSError):
        return None  # not a terminal, or a stream without a file descriptor
    rows, columns, x_pixels, y_pixels = struct.unpack("HHHH", report)
    return cell_shape(rows, columns, x_pixels, y_pixels)


def _screen_reader_running() -> bool:
    """Return True when Windows reports a running screen reader.

    Screen readers set this system flag so applications can trade graphics
    for text. Other systems have no equivalent the CLI can read cheaply, and
    ``BOILERPLATE_ACCESSIBLE`` covers them.
    """
    if sys.platform != "win32":
        return False
    running = ctypes.c_int()
    reported = ctypes.windll.user32.SystemParametersInfoW(
        _SPI_GETSCREENREADER, 0, ctypes.byref(running), 0
    )
    return bool(reported) and bool(running.value)
