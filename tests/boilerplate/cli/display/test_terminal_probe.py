"""Tests for reading the terminal facts the banner decides on.

Expected values come from docs/design/05-cli-reference.md §Banner: the
conditions that suppress it, that limit it to ASCII, and that rule out braille,
and the plausibility test for a reported pixel size.
"""

import ctypes
import io
import os
import struct
import sys
from types import SimpleNamespace

import pytest
from pytest_mock import MockerFixture
from rich.console import Console

from boilerplate.cli.display.terminal_probe import (
    _screen_reader_running,  # pyright: ignore[reportPrivateUsage]
    cell_shape,
    read_terminal_facts,
)

if sys.platform != "win32":
    import fcntl
    import termios


class _Terminal(io.StringIO):
    """A stdout stand-in that reports itself as a terminal."""

    def isatty(self) -> bool:
        return True


class _Cp1252Terminal(_Terminal):
    """A terminal stdout that encodes a Windows legacy code page."""

    encoding = "cp1252"  # pyright: ignore[reportIncompatibleVariableOverride]


class _NoIsatty:
    """A bare stdout stand-in without ``isatty``, as some embedding hosts install."""

    encoding = "utf-8"

    def write(self, text: str) -> int:
        return len(text)

    def flush(self) -> None:
        pass


class _User32:
    """Stands in for Windows' user32, answering SystemParametersInfoW."""

    def __init__(self, running: int, succeeds: int = 1) -> None:
        self.running = running
        self.succeeds = succeeds
        self.actions: list[int] = []

    def SystemParametersInfoW(  # noqa: N802  # the Win32 function's own name
        self, action: int, _param: int, flag: object, _ini: int
    ) -> int:
        self.actions.append(action)
        flag._obj.value = self.running  # type: ignore[attr-defined]  # ctypes.byref's target
        return self.succeeds


def _on_windows(monkeypatch: pytest.MonkeyPatch, user32: _User32) -> None:
    """Make the probe see Windows, with ``user32`` behind ctypes.windll."""
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(ctypes, "windll", SimpleNamespace(user32=user32), raising=False)


def _console(**kwargs: object) -> Console:
    """Return a modern 120 by 40 terminal console, with ``kwargs`` applied.

    ``legacy_windows`` is pinned off: on a Windows process without VT support
    Rich would keep the last column free, which is the host's fact, not the
    probe's.
    """
    options: dict[str, object] = {
        "file": _Terminal(),
        "width": 120,
        "height": 40,
        "legacy_windows": False,
    }
    return Console(**(options | kwargs))  # pyright: ignore[reportArgumentType]


@pytest.fixture(autouse=True)
def _plain_host(monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    """Pin the host-dependent inputs: TERM, NO_COLOR and the screen reader."""
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.delenv("NO_COLOR", raising=False)
    mocker.patch(
        "boilerplate.cli.display.terminal_probe._screen_reader_running",
        return_value=False,
    )


class TestInteractive:
    def test_a_terminal_stdout_is_interactive(self) -> None:
        assert read_terminal_facts(_console()).interactive is True

    def test_a_captured_stdout_is_not(self) -> None:
        facts = read_terminal_facts(_console(file=io.StringIO()))

        assert facts.interactive is False

    def test_a_stdout_without_isatty_is_not(self) -> None:
        assert read_terminal_facts(_console(file=_NoIsatty())).interactive is False

    def test_a_closed_stdout_is_not(self) -> None:
        """A closed stream raises when asked; the probe takes it as none."""
        closed = io.StringIO()
        closed.close()

        assert read_terminal_facts(_console(file=closed)).interactive is False

    @pytest.mark.parametrize("term", ["dumb", "unknown"])
    def test_a_dumb_terminal_is_not(
        self, monkeypatch: pytest.MonkeyPatch, term: str
    ) -> None:
        monkeypatch.setenv("TERM", term)

        assert read_terminal_facts(_console()).interactive is False


class TestSize:
    def test_comes_from_the_console(self) -> None:
        facts = read_terminal_facts(_console(width=90, height=33))

        assert (facts.columns, facts.lines) == (90, 33)


class TestBraille:
    def test_a_utf8_terminal_draws_braille(self) -> None:
        assert read_terminal_facts(_console()).braille is True

    def test_the_linux_text_console_does_not(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TERM", "linux")

        assert read_terminal_facts(_console()).braille is False

    def test_a_legacy_code_page_does_not(self) -> None:
        facts = read_terminal_facts(_console(file=_Cp1252Terminal()))

        assert facts.braille is False

    def test_the_encoding_stdout_had_before_utf8_was_forced_decides(self) -> None:
        """The console reads UTF-8 once the CLI forces it; the terminal did not."""
        facts = read_terminal_facts(_console(), encoding="cp1252")

        assert facts.braille is False

    def test_an_unknown_encoding_does_not(self) -> None:
        facts = read_terminal_facts(_console(), encoding="no-such-codec")

        assert facts.braille is False


class TestAsciiOnly:
    @pytest.mark.parametrize(("no_color", "ascii_only"), [(True, True), (False, False)])
    def test_follows_whether_the_console_prints_without_color(
        self, no_color: bool, ascii_only: bool
    ) -> None:
        facts = read_terminal_facts(_console(no_color=no_color))

        assert facts.ascii_only is ascii_only


class TestAccessible:
    def test_boilerplate_accessible_counts(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("BOILERPLATE_ACCESSIBLE", "1")

        assert read_terminal_facts(_console()).accessible is True

    def test_a_running_screen_reader_counts(self, mocker: MockerFixture) -> None:
        mocker.patch(
            "boilerplate.cli.display.terminal_probe._screen_reader_running",
            return_value=True,
        )

        assert read_terminal_facts(_console()).accessible is True

    def test_neither_is_not_accessible(self) -> None:
        assert read_terminal_facts(_console()).accessible is False


class TestScreenReaderRunning:
    """Ask Windows whether a screen reader runs (SPI_GETSCREENREADER, 0x0046)."""

    def test_asks_windows_for_the_screen_reader_flag(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user32 = _User32(running=0)
        _on_windows(monkeypatch, user32)

        _screen_reader_running()

        assert user32.actions == [0x0046]

    def test_a_reported_screen_reader_is_running(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _on_windows(monkeypatch, _User32(running=1))

        assert _screen_reader_running() is True

    @pytest.mark.parametrize(
        ("running", "succeeds"),
        [pytest.param(0, 1, id="flag-off"), pytest.param(1, 0, id="call-failed")],
    )
    def test_no_flag_or_a_failed_call_is_not(
        self, monkeypatch: pytest.MonkeyPatch, running: int, succeeds: int
    ) -> None:
        _on_windows(monkeypatch, _User32(running=running, succeeds=succeeds))

        assert _screen_reader_running() is False

    def test_other_systems_report_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "platform", "linux")

        assert _screen_reader_running() is False


class TestOptedOut:
    """``BOILERPLATE_NO_BANNER`` follows the ``BOILERPLATE_*`` truthiness rule."""

    @pytest.mark.parametrize(
        ("value", "opted_out"),
        [("1", True), ("yes", True), ("0", False), ("FALSE", False), (" ", False)],
    )
    def test_reads_the_env_var(
        self, monkeypatch: pytest.MonkeyPatch, value: str, opted_out: bool
    ) -> None:
        monkeypatch.setenv("BOILERPLATE_NO_BANNER", value)

        assert read_terminal_facts(_console()).opted_out is opted_out


class TestCellShape:
    def test_is_cell_height_over_cell_width(self) -> None:
        # 80 columns of 8 pixels, 24 rows of 18 pixels.
        assert cell_shape(rows=24, columns=80, x_pixels=640, y_pixels=432) == 2.25

    @pytest.mark.parametrize(
        ("x_pixels", "y_pixels"),
        [
            pytest.param(0, 0, id="unreported"),
            pytest.param(159, 432, id="under-2-pixels-per-column"),
            pytest.param(640, 95, id="under-4-pixels-per-row"),
        ],
    )
    def test_an_implausible_report_is_unknown(
        self, x_pixels: int, y_pixels: int
    ) -> None:
        assert cell_shape(24, 80, x_pixels, y_pixels) is None

    @pytest.mark.parametrize(
        ("x_pixels", "y_pixels"),
        [
            pytest.param(160, 432, id="exactly-2-pixels-per-column"),
            pytest.param(640, 96, id="exactly-4-pixels-per-row"),
        ],
    )
    def test_a_report_at_the_plausibility_floor_counts(
        self, x_pixels: int, y_pixels: int
    ) -> None:
        assert cell_shape(24, 80, x_pixels, y_pixels) is not None

    @pytest.mark.parametrize(("rows", "columns"), [(0, 80), (24, 0)])
    def test_a_window_without_rows_or_columns_is_unknown(
        self, rows: int, columns: int
    ) -> None:
        assert cell_shape(rows, columns, 640, 432) is None

    def test_a_captured_stdout_reports_no_shape(self) -> None:
        facts = read_terminal_facts(_console(file=io.StringIO()))

        assert facts.cell_shape is None

    if sys.platform != "win32":  # TIOCGWINSZ and pseudo-terminals are POSIX-only

        def test_a_pty_reports_the_shape_of_its_window(self) -> None:
            primary, secondary = os.openpty()
            size = struct.pack("HHHH", 24, 80, 640, 432)
            fcntl.ioctl(secondary, termios.TIOCSWINSZ, size)
            with os.fdopen(secondary, "w") as tty:
                facts = read_terminal_facts(_console(file=tty))
            os.close(primary)

            assert facts.cell_shape == 2.25
