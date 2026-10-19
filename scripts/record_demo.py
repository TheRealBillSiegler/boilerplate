"""Record the demo scenario, a banner title card then ``boilerplate new``, as a cast.

Drives the scenario the docs home page and the README show through a real
pseudo-terminal (via pexpect) running PowerShell, the shell the demo is
meant to look like: PSReadLine colours the command line as a viewer types
it, exactly as it does on a workstation. Every wait is a match against the
shell's or Copier's own output stream, so a changed prompt or a failed step
fails the recording loudly instead of shipping a stale demo. The questions
it answers are the table ``_QUESTIONS``, which
``tests/scripts/test_record_demo.py`` checks against the project template's
own question list, so a question added to the template fails the local gate
before it can stall a recording.

PSReadLine asks the terminal where the cursor is before it draws anything
(a ``CSI 6 n`` request that a terminal emulator answers with ``CSI row ;
col R``). Nothing sits on the other end of a pexpect pty, so this module
keeps an emulated screen (pyte) fed with everything the shell prints and
answers each request itself; without an answer PSReadLine draws at the
wrong position or stalls.

The recording opens on a title card: the CLI's own banner, drawn by
``build_banner`` and written straight into the cast ahead of the shell's
first prompt, with no command typed. It then clears to that prompt.

pexpect's pty backend is POSIX-only, so the functions that spawn and drive
the shell import it locally. The module itself stays importable everywhere;
only running it requires Linux.

Usage:
    python scripts/record_demo.py docs/assets/demo/boilerplate-new.cast

Writes the cast and, next to it, ``boilerplate-new-cast.js``: the same
recording wrapped as a JavaScript string for the docs home page.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Final, NamedTuple

import pyte
from rich.console import Console

from boilerplate.cli.display.banner import build_banner
from boilerplate.cli.display.terminal_facts import TerminalFacts

if TYPE_CHECKING:
    import pexpect

# A common terminal height, with room around the 11-row title card.
_ROWS: Final = 28
_COLS: Final = 100
_TYPE_DELAY_S: Final = 0.045
_IDLE_TIME_LIMIT_S: Final = 2.0
_DRAIN_TIMEOUT_S: Final = 0.02
# Pauses a viewer needs: to read a question before the answer is typed, and
# to read each finished screen (the title card, the render's summary, the
# test result) before the next command or the loop. A read pause fits under
# the idle cap; a linger is longer and goes through ``_EventRecorder.linger``
# (the title card through ``_EventRecorder.open_on``) so the cap does not
# shorten it.
_READ_PAUSE_S: Final = 0.4
_TITLE_LINGER_S: Final = 3.0
_AFTER_RENDER_LINGER_S: Final = 3.0
_END_LINGER_S: Final = 4.0

# Brand theme, matching docs/stylesheets/extra.css. The asciicast v2 theme
# object supports only fg/bg/palette (no separate cursor color). Every
# palette entry but the first, which is the background, holds at least 4.5:1
# on the background (WCAG AA for normal text); bright black (index 8) is
# lightened for that, as the usual dim grey is 2.77:1.
_THEME: Final[dict[str, str]] = {
    "fg": "#e6e8eb",
    "bg": "#1f2124",
    "palette": ":".join(
        [
            "#1f2124",
            "#f08a86",
            "#7fcf8e",
            "#e2c25f",
            "#40b4e5",
            "#c7a4ff",
            "#5fd3d8",
            "#e6e8eb",
            "#848e9b",
            "#f5a5a2",
            "#9fe0aa",
            "#ead588",
            "#7fcbef",
            "#d9c0ff",
            "#8be3e7",
            "#ffffff",
        ]
    ),
}

# Runs before the interactive session starts (pwsh -NoExit -Command). The
# prompt shows "PS ~/repos" plus the path below $DEMO_ROOT; a failed command
# appends "[exit N]" before the arrow, and the recorder's own prompt checks
# treat that text as a failure. PSReadLine's defaults are kept for colours
# (the command in yellow is the point of running PowerShell) but its
# history file, predictions, and bell are switched off so nothing from the
# runner leaks into the recording.
_SHELL_SETUP: Final = (
    "function global:prompt { $s = if ($?) { '' } else { ' [exit ' + $LASTEXITCODE + ']' }; "
    "'PS ~/repos' + $PWD.Path.Substring($env:DEMO_ROOT.Length) + $s + '> ' }; "
    "Set-PSReadLineOption -PredictionSource None -BellStyle None -HistorySaveStyle SaveNothing"
)

# The cursor-position request (DSR 6) the shell sends and the reporter answers.
_CPR_REQUEST: Final = "\x1b[6n"
# The title card hides the cursor; the clear after it shows the cursor again
# and homes it on a blank screen, the screen the shell started on.
_HIDE_CURSOR: Final = "\x1b[?25l"
_CLEAR_SCREEN: Final = "\x1b[?25h\x1b[2J\x1b[H"

# An SGR sequence (CSI params m) and the 256-colour dark red (xterm index 124,
# #af0000, 2.17:1 on the theme background) that a tool can ask for in one. The
# theme palette cannot remap a 256-colour index, but it does remap SGR 31.
_SGR_RE: Final = re.compile(r"\x1b\[([0-9;]*)m")
_DARK_RED_256_PARAMS: Final = ("38", "5", "124")
_RED_PARAM: Final = "31"
# SGR 38 and 48 introduce an extended color: "5;n" (256-colour) or "2;r;g;b"
# (truecolor). The mode's arguments are numbers, not further SGR parameters.
_EXTENDED_COLOR_PARAMS: Final = frozenset({"38", "48"})
_EXTENDED_COLOR_ARGS: Final = {"5": 2, "2": 4}

_FAILED_PROMPT_RE: Final = r"\[exit -?\d*\]> "
# The bare prompt may be followed by escape sequences PSReadLine sends the
# moment it takes over the line (the cursor-position request above, cursor
# visibility toggles), so the anchor tolerates a run of CSI sequences.
_BARE_PROMPT_RE: Final = r"PS ~/repos\S*> (?:\x1b\[[0-9;?]*[A-Za-z])*$"


class _Question(NamedTuple):
    """Pair a Copier question with the answer the scenario gives it.

    A plain tuple rather than a model: the values are constants read only by
    this script, so there is no boundary to validate at.

    Attributes:
        pattern: Regular expression matched against the question text as it
            arrives on the pty; a substring of the template's ``help``.
        answer: Replacement for the pre-filled default (cleared with Ctrl+U
            first); ``None`` accepts the default as-is.
        timeout: Seconds to wait for ``pattern`` to appear.
        mark: Optional marker label recorded once ``pattern`` appears.
    """

    pattern: str
    answer: str | None
    timeout: float = 30.0
    mark: str | None = None


# The project template's questions in the order Copier asks them (see
# src/boilerplate/templates/project/copier.yml). The first wait is longer:
# it also covers whatever ``new`` loads before its first question.
_QUESTIONS: Final[tuple[_Question, ...]] = (
    _Question(
        "name of the project", "Weather Report", timeout=60.0, mark="first question"
    ),
    _Question("brief description", "Daily forecast summaries for the team."),
    _Question("runtime dependencies", None),
    _Question("development dependencies", None),
    _Question("sample module", None),
    _Question("first and last name", "Bill Siegler"),
    _Question("email address", "bill@example.com"),
    _Question("Package index URL", None),
)


def _use_theme_red(data: str) -> str:
    r"""Rewrite the 256-colour dark red in ``data`` to the 16-colour red.

    The cast's theme sets the 16 ANSI colours to values that clear 4.5:1 on its
    background, but cannot reach a 256-colour index, so the dark red a tool asks
    for as ``38;5;124`` stays at 2.17:1. A rewrite to SGR 31 shows the theme's
    red instead. A sequence split across two reads of the pty is not rewritten.

    Args:
        data: A chunk of terminal output.

    Returns:
        ``data`` with each ``38;5;124`` foreground color replaced by ``31``.
        A background (``48``) and the arguments of a truecolor
        (``38;2;r;g;b``) are left as written.

    Examples:
        >>> _use_theme_red("\x1b[1;38;5;124mx\x1b[0m")
        '\x1b[1;31mx\x1b[0m'
    """

    def rewrite(match: re.Match[str]) -> str:
        params = match.group(1).split(";")
        out: list[str] = []
        index = 0
        while index < len(params):
            if tuple(params[index : index + 3]) == _DARK_RED_256_PARAMS:
                out.append(_RED_PARAM)
                index += 3
                continue
            width = 1
            if params[index] in _EXTENDED_COLOR_PARAMS and index + 1 < len(params):
                width += _EXTENDED_COLOR_ARGS.get(params[index + 1], 0)
            out.extend(params[index : index + width])
            index += width
        return f"\x1b[{';'.join(out)}m"

    return _SGR_RE.sub(rewrite, data)


class DemoRecordingError(Exception):
    """Raised when the demo scenario deviates from its expected script."""


class _EventRecorder:
    """Collects asciicast v2 output/marker events with capped idle gaps.

    Attributes:
        events: Recorded ``(time_s, code, data)`` tuples in emission order.
    """

    def __init__(self, *, idle_cap_s: float) -> None:
        """Start a new recording clock.

        Args:
            idle_cap_s: Maximum gap, in seconds, credited between two
                consecutive events regardless of how long the real wait
                was — keeps the file's recorded duration bounded even when
                a step (uv sync, pytest) takes a while in CI.
        """
        self._idle_cap_s = idle_cap_s
        self._virtual_time_s = 0.0
        self._last_wall_time_s = time.monotonic()
        self.events: list[tuple[float, str, str]] = []

    @property
    def virtual_time_s(self) -> float:
        """Returns the recorder's current (capped) elapsed time, in seconds."""
        return self._virtual_time_s

    def _advance(self) -> float:
        now = time.monotonic()
        gap_s = min(now - self._last_wall_time_s, self._idle_cap_s)
        self._last_wall_time_s = now
        self._virtual_time_s += max(gap_s, 0.0)
        return self._virtual_time_s

    def restart(self) -> None:
        """Move every event recorded so far to time zero and restarts the clock.

        Called once the shell's first prompt is up: what came before it
        (PowerShell's start-up, well under the idle cap but a blank screen
        all the same) is not part of the demo, and the recording should
        open on the prompt.
        """
        self.events = [(0.0, code, data) for _, code, data in self.events]
        self._virtual_time_s = 0.0
        self._last_wall_time_s = time.monotonic()

    def open_on(self, screen: str, seconds: float) -> None:
        """Open the recording on ``screen``, held for ``seconds`` before the rest.

        Everything recorded so far moves to the end of the hold, after a
        clear, so it plays on the blank screen it was first drawn on. The
        hold takes no real time; like ``linger``, it records an empty event
        at each step the idle cap allows.

        Args:
            screen: Terminal output to open on.
            seconds: How long the viewer gets, in recorded time.
        """
        hold: list[tuple[float, str, str]] = [(0.0, "o", screen)]
        step_s = self._idle_cap_s
        while step_s < seconds:
            hold.append((step_s, "o", ""))
            step_s += self._idle_cap_s
        hold.append((seconds, "o", _CLEAR_SCREEN))
        self.events = hold + [
            (moment_s + seconds, code, data) for moment_s, code, data in self.events
        ]
        self._virtual_time_s += seconds

    def output(self, s: str) -> None:
        """Record a chunk of terminal output at the current recorder time.

        The dark red of a 256-colour sequence is rewritten to the theme's red
        first (see ``_use_theme_red``); the cast is what the viewer sees, so
        the shell and the cursor reporter still get the bytes as written.

        Args:
            s: A chunk of data just read from the shell's pty.
        """
        if s:
            self.events.append((self._advance(), "o", _use_theme_red(s)))

    def mark(self, label: str) -> None:
        """Record a labeled marker event at the current recorder time.

        Args:
            label: The marker's label (rendered as a named chapter by
                asciinema-player).
        """
        self.events.append((self._advance(), "m", label))

    def hold(self) -> None:
        """Record an empty output event so the recording ends at the current time.

        The player and the gif renderer treat the last event as the end of
        the recording, so a pause after the final output only survives if
        something is recorded at the end of it.
        """
        self.events.append((self._advance(), "o", ""))

    def linger(self, seconds: float, wait: Callable[[float], object]) -> None:
        """Pause for ``seconds`` and credit all of it, in steps the idle cap allows.

        A slow step is clamped to the idle cap on purpose; a deliberate pause
        is not. ``wait`` passes the real time (reading the pty keeps the
        cursor reporter answering), and an empty output event closes each
        step, so no gap in the file exceeds the cap the header and the player
        clamp to.

        Args:
            seconds: How long the viewer gets, in recorded time.
            wait: Called with the seconds each step takes; returns once they
                have passed.
        """
        remaining = seconds
        while remaining > 0:
            step = min(self._idle_cap_s, remaining)
            wait(step)
            self.hold()
            remaining -= step


class _CursorReporter:
    """Answers cursor-position requests from an emulated copy of the screen.

    Everything the shell prints is fed to a pyte screen of the recording's
    size, so when a ``CSI 6 n`` arrives the reply names the same cell a real
    terminal would. A request split across two reads is reassembled before
    it is answered.
    """

    def __init__(self, *, rows: int, cols: int, reply: Callable[[str], object]) -> None:
        """Create the emulated screen.

        Args:
            rows: Screen height, in character cells.
            cols: Screen width, in character cells.
            reply: Called with each answer, which it must deliver to the
                shell's input.
        """
        self._screen = pyte.Screen(cols, rows)
        self._stream = pyte.Stream(self._screen)
        self._reply = reply
        self._pending = ""

    def observe(self, s: str) -> None:
        """Feed a chunk of shell output to the screen, answering any requests.

        Args:
            s: A chunk of data just read from the shell's pty.
        """
        data = self._pending + s
        self._pending = ""
        while (at := data.find(_CPR_REQUEST)) >= 0:
            self._stream.feed(data[:at])
            cursor = self._screen.cursor
            self._reply(f"\x1b[{cursor.y + 1};{cursor.x + 1}R")
            data = data[at + len(_CPR_REQUEST) :]
        # Hold back a tail that could be the start of a request cut in two.
        for keep in range(min(len(_CPR_REQUEST) - 1, len(data)), 0, -1):
            if _CPR_REQUEST.startswith(data[-keep:]):
                self._pending = data[-keep:]
                data = data[:-keep]
                break
        self._stream.feed(data)


class _PtyObserver:
    """Routes each chunk pexpect reads to the recorder and the cursor reporter.

    Implements the ``write``/``flush`` protocol pexpect expects of a
    ``logfile_read`` object.
    """

    def __init__(self, recorder: _EventRecorder, reporter: _CursorReporter) -> None:
        """Pairs the recorder with the reporter.

        Args:
            recorder: Receives every chunk as an output event.
            reporter: Receives every chunk to keep its screen current.
        """
        self._recorder = recorder
        self._reporter = reporter

    def write(self, s: str, /) -> object:
        """Implement the pexpect ``logfile_read`` write protocol.

        Args:
            s: A chunk of data pexpect just read from the child's output.

        Returns:
            None, satisfying the ``_Logfile`` protocol's ``object`` return.
        """
        self._recorder.output(s)
        self._reporter.observe(s)
        return None

    def flush(self) -> object:
        """Implement the pexpect ``logfile_read`` flush protocol (a no-op)."""
        return None


def _title_card() -> str:
    """Return the title card: the CLI's banner, centered on the recording's screen.

    Returns:
        Terminal output that draws the banner, colored as the CLI colors it,
        with the cursor hidden.

    Raises:
        DemoRecordingError: The banner does not fit the recording's size.
    """
    facts = TerminalFacts(
        interactive=True,
        columns=_COLS,
        lines=_ROWS,
        braille=True,
        ascii_only=False,
        accessible=False,
        opted_out=False,
    )
    banner = build_banner(facts)
    if banner is None:
        msg = f"the banner does not fit a {_COLS}x{_ROWS} recording"
        raise DemoRecordingError(msg)
    console = Console(
        force_terminal=True, color_system="truecolor", width=_COLS, legacy_windows=False
    )
    with console.capture() as capture:
        console.print(banner, end="")
    rows = capture.get().split("\n")
    width = max(len(row) for row in banner.plain.split("\n"))
    left = " " * ((_COLS - width) // 2)
    above = "\r\n" * ((_ROWS - len(rows)) // 2)
    return _HIDE_CURSOR + above + "\r\n".join(left + row for row in rows)


def _write_cast(
    path: Path, events: list[tuple[float, str, str]], *, duration_s: float
) -> None:
    """Write ``events`` to ``path`` as a complete asciicast v2 file.

    Writes to a sibling temp file and replaces ``path`` atomically, so a
    reader never observes a partially written cast.

    Args:
        path: Destination ``.cast`` file path.
        events: Recorded ``(time_s, code, data)`` tuples, in order.
        duration_s: The recording's total (idle-capped) duration.
    """
    header: dict[str, object] = {
        "version": 2,
        "width": _COLS,
        "height": _ROWS,
        "timestamp": int(time.time()),
        "duration": round(duration_s, 6),
        "idle_time_limit": _IDLE_TIME_LIMIT_S,
        "env": {"SHELL": "/usr/bin/pwsh", "TERM": "xterm-256color"},
        "theme": _THEME,
    }
    tmp_path = path.with_name(path.name + ".tmp")
    with tmp_path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(header) + "\n")
        for moment_s, code, data in events:
            fh.write(json.dumps([round(moment_s, 6), code, data]) + "\n")
    tmp_path.replace(path)


def _cast_js_path(cast_path: Path) -> Path:
    """Return where the JavaScript wrapper for ``cast_path`` is written.

    Args:
        cast_path: The ``.cast`` file path.

    Returns:
        A sibling path ending in ``-cast.js`` (``boilerplate-new.cast``
        becomes ``boilerplate-new-cast.js``).
    """
    return cast_path.with_name(f"{cast_path.stem}-cast.js")


def _write_cast_js(cast_path: Path) -> None:
    """Wrap the cast at ``cast_path`` as a JavaScript string next to it.

    The docs home page loads the recording through a plain ``<script src>``
    tag instead of letting the player fetch the ``.cast`` file: fetch() of a
    relative path is blocked from a null origin, which is what the offline
    bundle opens from (file://), and a script tag has no such restriction.

    Args:
        cast_path: The ``.cast`` file to wrap; must already exist.
    """
    cast = cast_path.read_text(encoding="utf-8")
    js = (
        f"// Generated by scripts/record_demo.py from {cast_path.name} -- do not\n"
        "// hand-edit; re-run the recorder to regenerate both files.\n"
        "//\n"
        "// Embedded as a JS string (loaded via a normal <script src> tag)\n"
        "// instead of being fetch()ed by the player: fetch() is blocked from a\n"
        "// null origin, so this is what lets the offline bundle play the\n"
        "// recording from file://.\n"
        f"window.BOILERPLATE_DEMO_CAST = {json.dumps(cast)};\n"
    )
    _cast_js_path(cast_path).write_text(js, encoding="utf-8", newline="\n")


class _Session:
    """Bundles the spawned shell with its event recorder for helper functions.

    Attributes:
        child: The spawned shell.
        recorder: The event recorder receiving the shell's output.
    """

    def __init__(self, child: pexpect.spawn[str], recorder: _EventRecorder) -> None:
        """Pairs a spawned shell with its recorder.

        Args:
            child: The spawned shell.
            recorder: The event recorder receiving the shell's output.
        """
        self.child = child
        self.recorder = recorder


def _settle(child: pexpect.spawn[str], seconds: float) -> None:
    """Keep reading the child's output for ``seconds``, then returns.

    The pause the recording needs is the same either way, but reading
    through it (rather than sleeping) lets the cursor reporter answer a
    position request the shell sends during the pause; a request left
    unanswered until the next keystroke would stall PSReadLine and can cost
    the keystroke itself.

    Args:
        child: The spawned shell.
        seconds: How long to keep reading.
    """
    import pexpect  # noqa: PLC0415 -- deferred: pexpect is POSIX-only (see module docstring)

    # child.expect(pexpect.TIMEOUT, ...) reads through the same Expecter
    # loop as every other expect() call, so drained bytes still land in
    # child.buffer (and are still logged to the observer); a direct
    # child.read_nonblocking() loop bypasses that buffer entirely and
    # silently drops whatever it reads, which starves the next _ask()'s
    # expect() of text it never saw.
    child.expect(pexpect.TIMEOUT, timeout=seconds)


def _drain(child: pexpect.spawn[str]) -> None:
    """Read whatever the child has already echoed, without blocking long.

    Called between individual keystrokes so each character's echo lands in
    the recording with its own real timestamp, instead of arriving as one
    burst the next time ``expect`` happens to read the pty.

    Args:
        child: The spawned shell.
    """
    _settle(child, _DRAIN_TIMEOUT_S)


def _type_slowly(child: pexpect.spawn[str], text: str) -> None:
    """Send ``text`` one character at a time at a fixed cadence.

    Keystrokes are paced, not synchronised with their echoes: each one is
    followed by ``_TYPE_DELAY_S`` of reading, which records the echo with
    its own timestamp as it arrives and answers any cursor-position request
    in between. Waiting for each echo before sending the next key would
    hand PSReadLine a pause of more than 50 ms between keys, and it then
    checks for a resized window before every redraw by asking where the
    cursor is (see ``Render`` in PSReadLine's Render.cs), which roughly
    doubled the cost of every keystroke; keys that arrive inside that
    window are drawn straight away.

    Args:
        child: The spawned shell.
        text: The text to type.
    """
    for ch in text:
        child.send(ch)
        _settle(child, _TYPE_DELAY_S)


def _press_enter(child: pexpect.spawn[str]) -> None:
    """Send a carriage return and drains its echo.

    Args:
        child: The spawned shell.
    """
    child.send("\r")
    _drain(child)


def _clear_and_type(child: pexpect.spawn[str], answer: str) -> None:
    """Clear a pre-filled default (Ctrl+U) then types and submits ``answer``.

    Args:
        child: The spawned shell.
        answer: The replacement answer to type and submit.
    """
    child.sendcontrol("u")
    _drain(child)
    _type_slowly(child, answer)
    _press_enter(child)


def _expect_prompt(child: pexpect.spawn[str], *, timeout: float) -> None:
    """Wait for the bare shell prompt; raises if it shows a failed exit.

    Args:
        child: The spawned shell.
        timeout: Seconds to wait for the prompt to reappear.

    Raises:
        DemoRecordingError: The prompt reappeared showing a non-zero exit
            status.
    """
    idx = child.expect([_FAILED_PROMPT_RE, _BARE_PROMPT_RE], timeout=timeout)
    if idx == 0:
        raise DemoRecordingError(
            "shell prompt reported a non-zero exit status mid-scenario"
        )


def _ask(session: _Session, question: _Question) -> None:
    """Wait for a Copier question, mark it if asked, then answer it.

    Args:
        session: The shell and its event recorder.
        question: What to wait for and how to answer it.
    """
    session.child.expect(question.pattern, timeout=question.timeout)
    if question.mark:
        session.recorder.mark(question.mark)
    _settle(session.child, _READ_PAUSE_S)
    if question.answer is None:
        _press_enter(session.child)
    else:
        _clear_and_type(session.child, question.answer)


def _spawn_shell(recorder: _EventRecorder, demo_root: Path) -> pexpect.spawn[str]:
    """Spawns the interactive PowerShell session the scenario runs in.

    Args:
        recorder: The event recorder that receives the shell's output.
        demo_root: Working directory the shell starts in, and the value
            the prompt strips from ``$PWD`` (see ``_SHELL_SETUP``).

    Returns:
        The spawned shell, already wired to ``recorder`` and to a cursor
        reporter that answers its position requests.
    """
    import pexpect  # noqa: PLC0415 -- deferred: pexpect is POSIX-only (see module docstring)

    env = {
        **os.environ,
        "TERM": "xterm-256color",
        "DEMO_ROOT": str(demo_root),
        # Copier's prompts run on prompt_toolkit, which also asks for the
        # cursor position and prints a warning when the answer is slow;
        # switch its request off rather than rely on the reporter's timing.
        "PROMPT_TOOLKIT_NO_CPR": "1",
        # Neither the update notice nor telemetry belongs in the demo.
        "POWERSHELL_UPDATECHECK": "Off",
        "POWERSHELL_TELEMETRY_OPTOUT": "1",
    }
    # The recorded shell must find the `boilerplate` installed as a uv tool
    # under the demo's home directory, not the repo checkout's .venv that
    # `uv run` put first on PATH; the tool's interpreter path is what
    # Copier prints when it runs the template's post-generation task.
    env["PATH"] = os.pathsep.join(
        [str(Path.home() / ".local" / "bin"), env.get("PATH", "")]
    )
    # uv run's own environment carries VIRTUAL_ENV (pointing at this
    # repo's .venv) and UV_RUN_RECURSION_DEPTH. The recorded shell's closing
    # `uv run pytest -q` reads VIRTUAL_ENV, finds it doesn't match
    # weather-report's own .venv, and prints a "will be ignored" warning
    # straight into the demo; drop both so the child starts as clean as a
    # real user's shell.
    env.pop("VIRTUAL_ENV", None)
    env.pop("UV_RUN_RECURSION_DEPTH", None)
    child: pexpect.spawn[str] = pexpect.spawn(
        "pwsh",
        ["-NoLogo", "-NoProfile", "-NoExit", "-Command", _SHELL_SETUP],
        cwd=str(demo_root),
        env=env,
        dimensions=(_ROWS, _COLS),
        encoding="utf-8",
        timeout=30,
    )
    # pexpect sleeps 50 ms before every send() by default (delaybeforesend),
    # which would pad each keystroke and, worse, each cursor-position reply;
    # PSReadLine waits for that reply before it draws.
    child.delaybeforesend = None
    reporter = _CursorReporter(rows=_ROWS, cols=_COLS, reply=child.send)
    child.logfile_read = _PtyObserver(recorder, reporter)
    return child


def _record_scenario(cast_path: Path) -> None:
    """Drive the demo scenario through a real PTY and write the cast file.

    Scenario: the banner title card, then ``boilerplate new project
    weather-report``, answering each Copier question, then ``cd
    weather-report && uv run pytest -q``. The
    cast and its JavaScript wrapper are written only after every step
    succeeds; callers must delete them themselves on failure (nothing is
    written here in that case).

    Args:
        cast_path: Destination ``.cast`` file path.

    Raises:
        DemoRecordingError: The banner does not fit the recording, or the
            shell prompt reported a non-zero exit status after the render or
            the test run.
        pexpect.TIMEOUT: A prompt, the render, or the test run did not
            produce the expected output in time.
        pexpect.EOF: The shell exited unexpectedly.
    """
    recorder = _EventRecorder(idle_cap_s=_IDLE_TIME_LIMIT_S)
    title_card = _title_card()
    # Recorded under the real home directory rather than a temp path: the
    # template's post-generation task prints the absolute repository path,
    # and a demo that says /tmp does not look like anyone's workstation.
    demo_root = Path.home() / "repos"
    demo_root.mkdir(parents=True, exist_ok=True)
    project_dir = demo_root / "weather-report"
    if project_dir.exists():
        msg = f"{project_dir} already exists; refusing to record over it"
        raise DemoRecordingError(msg)
    child = _spawn_shell(recorder, demo_root)
    session = _Session(child, recorder)

    try:
        _expect_prompt(child, timeout=30)
        recorder.restart()
        recorder.open_on(title_card, _TITLE_LINGER_S)
        _settle(child, _READ_PAUSE_S)

        def wait(seconds: float) -> None:
            _settle(child, seconds)

        # The first question's longer wait also covers the CLI's cold start.
        _type_slowly(child, "boilerplate new project weather-report")
        _press_enter(child)

        for question in _QUESTIONS:
            _ask(session, question)

        # Rich prints display.success(...) with highlighting on (no
        # highlight=False, unlike the CLI's other console), so it may split
        # the line into SGR runs. The unquoted destination matches no
        # highlighter pattern today and stays in the same run as "Created";
        # the only split falls around the "(N layers)" suffix. Tolerate any
        # run of SGR codes between the word and the destination anyway, so
        # a highlighter change cannot stall the recording.
        child.expect(r"Created (?:\x1b\[[0-9;]*m)*weather-report", timeout=180)
        _expect_prompt(child, timeout=60)
        recorder.mark("render done")
        recorder.linger(_AFTER_RENDER_LINGER_S, wait)

        _type_slowly(child, "cd weather-report && uv run pytest -q")
        _press_enter(child)
        child.expect("passed", timeout=120)
        _expect_prompt(child, timeout=60)
        recorder.mark("tests done")
        recorder.linger(_END_LINGER_S, wait)
    finally:
        child.close(force=True)
        shutil.rmtree(project_dir, ignore_errors=True)

    _write_cast(cast_path, recorder.events, duration_s=recorder.virtual_time_s)
    _write_cast_js(cast_path)


def main(argv: list[str]) -> int:
    """Run the demo recording end-to-end.

    Args:
        argv: Command-line arguments; expects exactly one, the output
            ``.cast`` path.

    Returns:
        Process exit code: 0 on a complete, verified recording; 1 on bad
        usage or any scenario failure (timeout, EOF, or a non-zero exit
        status reported by the shell prompt). On failure, neither the cast
        nor its JavaScript wrapper is left at the destination.
    """
    if len(argv) != 1:
        print("usage: record_demo.py OUTPUT.cast", file=sys.stderr)
        return 1
    cast_path = Path(argv[0])

    try:
        _record_scenario(cast_path)
    except Exception as exc:
        print(f"demo recording failed: {exc}", file=sys.stderr)
        cast_path.unlink(missing_ok=True)
        cast_path.with_name(cast_path.name + ".tmp").unlink(missing_ok=True)
        _cast_js_path(cast_path).unlink(missing_ok=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


__all__ = ["DemoRecordingError", "main"]
