"""Check the demo recorder's question script against the project template.

The recorder answers each Copier question by waiting for its text on the pty,
so a question added to the template stalls every recording until the script
learns it. These tests fail on such a change before the recording does.
"""

import importlib.util
import re
from itertools import pairwise
from pathlib import Path

import pytest
import yaml

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
