"""Check the demo recorder's question script against the project template.

The recorder answers each Copier question by waiting for its text on the pty,
so a question added to the template stalls every recording until the script
learns it. This test fails on such a change before the recording does.
"""

import importlib.util
import re
from pathlib import Path

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


def _prompted_help_texts() -> list[str]:
    """Return the help text of every question the project template asks, in order."""
    spec = yaml.safe_load(_PROJECT_COPIER_YML.read_text(encoding="utf-8"))
    return [
        entry["help"]
        for key, entry in spec.items()
        if not key.startswith("_") and entry.get("when", True) is not False
    ]


class TestQuestionScript:
    def test_answers_every_prompted_question_in_order(self):
        helps = _prompted_help_texts()
        patterns = [question.pattern for question in record_demo._QUESTIONS]

        assert len(patterns) == len(helps), (
            f"the recorder answers {len(patterns)} questions but the template asks "
            f"{len(helps)}: {helps}"
        )
        for pattern, help_text in zip(patterns, helps, strict=True):
            assert re.search(pattern, help_text), (
                f"the recorder waits for {pattern!r} but the template asks {help_text!r}"
            )
