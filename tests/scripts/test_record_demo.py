"""Check the demo recorder's question script against the project template.

The recorder answers each Copier question by waiting for its text on the pty,
so a question added to the template stalls every recording until the script
learns it. These tests fail on such a change before the recording does.
"""

import importlib.util
import re
from itertools import pairwise
from pathlib import Path

import pyte
import pytest
import yaml

from boilerplate.cli.display.banner_art import NAME

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_MODULE_PATH = _REPO_ROOT / "scripts" / "record_demo.py"
_SPEC = importlib.util.spec_from_file_location("record_demo", _MODULE_PATH)
assert _SPEC is not None
assert _SPEC.loader is not None
record_demo = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(record_demo)

_PROJECT_COPIER_YML = (
    _REPO_ROOT / "src" / "boilerplate" / "templates" / "project" / "copier.yml"
)
# Copier prints its two-cell question mark and a space before the help text.
_PROMPT_PREFIX_CELLS = 3


def _prompted_help_texts() -> list[str]:
    """Return the help text of every question the project template asks, in order."""
    spec = yaml.safe_load(_PROJECT_COPIER_YML.read_text(encoding="utf-8"))
    helps: list[str] = []
    for key, entry in spec.items():
        if key.startswith("_"):
            continue
        when = entry.get("when", True)
        # Copier renders a templated `when` before deciding whether to ask. This
        # template only uses literal booleans; a templated one needs that
        # rendering here before it can be counted.
        assert isinstance(when, bool), f"{key}: templated `when` is not evaluated here"
        if when:
            helps.append(entry["help"])
    return helps


def _patterns() -> list[str]:
    return [question.pattern for question in record_demo._QUESTIONS]


class TestQuestionScript:
    def test_answers_every_prompted_question_in_order(self):
        helps = _prompted_help_texts()
        patterns = _patterns()

        assert len(patterns) == len(helps), (
            f"the recorder answers {len(patterns)} questions but the template asks "
            f"{len(helps)}: {helps}"
        )
        for pattern, help_text in zip(patterns, helps, strict=True):
            assert re.search(pattern, help_text), (
                f"the recorder waits for {pattern!r} but the template asks {help_text!r}"
            )

    def test_each_pattern_arrives_before_the_pty_wraps(self):
        # prompt_toolkit repositions the cursor before the character that lands
        # in the last column, so help text from there on is not contiguous in
        # the byte stream pexpect matches, although the screen shows it whole.
        for pattern, help_text in zip(_patterns(), _prompted_help_texts(), strict=True):
            match = re.search(pattern, help_text)
            assert match is not None
            assert _PROMPT_PREFIX_CELLS + match.end() < record_demo._COLS, (
                f"{pattern!r} would straddle the {record_demo._COLS}-column wrap"
            )


class _FakeClock:
    """A monotonic clock that only moves when a wait is simulated."""

    def __init__(self) -> None:
        self.now = 100.0

    def wait(self, seconds: float) -> None:
        self.now += seconds


def _lingering_recorder(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[record_demo._EventRecorder, _FakeClock]:
    clock = _FakeClock()
    monkeypatch.setattr(record_demo.time, "monotonic", lambda: clock.now)
    return record_demo._EventRecorder(idle_cap_s=2.0), clock


class TestLinger:
    """A deliberate pause is credited in full; only a slow step is clamped."""

    def test_a_pause_longer_than_the_cap_is_credited_in_full(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        recorder, clock = _lingering_recorder(monkeypatch)

        recorder.linger(5.0, clock.wait)

        assert recorder.virtual_time_s == 5.0

    def test_no_gap_in_the_recording_exceeds_the_cap(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        recorder, clock = _lingering_recorder(monkeypatch)

        recorder.linger(5.0, clock.wait)

        times = [0.0, *(time_s for time_s, _, _ in recorder.events)]
        assert max(later - earlier for earlier, later in pairwise(times)) <= 2.0
        assert all(code == "o" and data == "" for _, code, data in recorder.events)


class TestOpenOn:
    """The recording opens on a screen held ahead of everything recorded so far."""

    def _opened(self, monkeypatch: pytest.MonkeyPatch) -> list[tuple[float, str, str]]:
        recorder, _ = _lingering_recorder(monkeypatch)
        recorder.output("PS ~/repos> ")
        recorder.restart()
        recorder.open_on("TITLE", 5.0)
        return recorder.events

    def test_the_screen_is_the_first_event(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert self._opened(monkeypatch)[0] == (0.0, "o", "TITLE")

    def test_what_was_recorded_follows_the_hold_on_a_cleared_screen(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        events = self._opened(monkeypatch)

        assert events[-2] == (5.0, "o", record_demo._CLEAR_SCREEN)
        assert events[-1] == (5.0, "o", "PS ~/repos> ")

    def test_later_events_count_from_the_end_of_the_hold(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        recorder, clock = _lingering_recorder(monkeypatch)
        recorder.restart()
        recorder.open_on("TITLE", 5.0)

        clock.wait(1.0)
        recorder.output("x")

        assert recorder.events[-1] == (6.0, "o", "x")

    def test_no_gap_in_the_hold_exceeds_the_cap(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        times = [time_s for time_s, _, _ in self._opened(monkeypatch)]

        assert max(later - earlier for earlier, later in pairwise(times)) <= 2.0


def _screen_rows(text: str) -> list[str]:
    screen = pyte.Screen(record_demo._COLS, record_demo._ROWS)
    pyte.Stream(screen).feed(text)
    return screen.display


class TestTitleCard:
    """The title card is the CLI's own banner, whole and centered on one screen."""

    def test_the_card_shows_the_whole_name(self) -> None:
        rows = _screen_rows(record_demo._title_card())

        assert all(any(name_row.strip() in row for row in rows) for name_row in NAME)

    def test_the_card_shows_the_braille_logo(self) -> None:
        rows = _screen_rows(record_demo._title_card())

        assert any("⠀" <= char <= "⣿" for row in rows for char in row)

    def test_the_card_is_centered_across(self) -> None:
        drawn = [row for row in _screen_rows(record_demo._title_card()) if row.strip()]
        left = min(len(row) - len(row.lstrip()) for row in drawn)
        right = record_demo._COLS - max(len(row.rstrip()) for row in drawn)

        assert abs(left - right) <= 1

    def test_the_card_is_centered_down(self) -> None:
        rows = _screen_rows(record_demo._title_card())
        drawn = [i for i, row in enumerate(rows) if row.strip()]
        above = drawn[0]
        below = record_demo._ROWS - 1 - drawn[-1]

        assert abs(above - below) <= 1
