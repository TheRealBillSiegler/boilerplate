"""Whether the unified questionnaire can be driven interactively in-process.

S17 asks the family's diamond merged view with ``defaults=False`` through the
first layer's Worker, feeding keystrokes through prompt_toolkit's pipe input
with a dummy output, so no console is needed: clear the prefilled project
name and type a new one, then accept every other default. A spy on the
prompt function Copier calls records each question's default and whether it
was shown.
"""

import threading
from collections.abc import Iterator, Mapping, Sequence
from typing import Any, NamedTuple

import pytest
import questionary
from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

from tests.boilerplate.templates.conftest import ask_merged_questionnaire
from tests.integration.boilerplate.composition.family import Family
from tests.integration.boilerplate.composition.scenarios.builders import (
    temp_dir_inside,
    templates_at,
)

KEYSTROKES = "\x15Typed App\r" + "\r" * 12  # Ctrl-U clears the prefill.
GUARD_SECONDS = 90
# Core 1.1.0 asks `license`, which app 1.1.0 overrides; service overrides core's
# Python version.
PROMPTED = {"core": "1.1.0", "service": "1.0.0", "docs": "1.0.0", "app": "1.1.0"}


def _plain(default: object) -> object:
    """Return a choice question's default as the value of its choice."""
    return default.value if isinstance(default, questionary.Choice) else default


class Prompt(NamedTuple):
    """One question as Copier put it to the prompt."""

    name: str
    default: object
    shown: bool


class Session(NamedTuple):
    """What the interactive pass did."""

    finished: bool
    prompts: list[Prompt]
    answers: dict[str, Any]


@pytest.fixture(scope="module")
def session(
    family: Family, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[Session]:
    """Drive the unified questionnaire from pipe input on a worker thread."""
    root = tmp_path_factory.mktemp("prompting")
    templates = templates_at(family, root, PROMPTED)
    prompts: list[Prompt] = []
    answers: dict[str, Any] = {}
    real = questionary.unsafe_prompt

    def spy(
        questions: Sequence[Mapping[str, Any]],
        answers: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        given = dict(answers or {})
        for question in questions:
            when = question.get("when", True)
            shown = bool(when(given)) if callable(when) else bool(when)
            prompts.append(
                Prompt(str(question["name"]), _plain(question.get("default")), shown)
            )
        return real(questions, answers=answers)

    def ask() -> None:
        with (
            create_pipe_input() as pipe,
            create_app_session(input=pipe, output=DummyOutput()),
        ):
            pipe.send_text(KEYSTROKES)
            answers.update(
                ask_merged_questionnaire("app", {}, templates, defaults=False).user
            )

    with temp_dir_inside(root), pytest.MonkeyPatch.context() as patch:
        patch.setattr("copier._main.unsafe_prompt", spy)
        thread = threading.Thread(target=ask, daemon=True)
        thread.start()
        thread.join(timeout=GUARD_SECONDS)
        yield Session(not thread.is_alive(), prompts, answers)


@pytest.mark.xdist_group("S17")
class TestInteractivePrompting:
    """S17: the unified questionnaire under pipe input."""

    def test_pass_finishes_and_takes_the_typed_answer(self, session: Session) -> None:
        """S17: the pass runs without a console and returns the typed name."""
        assert (session.finished, session.answers.get("project_name")) == (
            True,
            "Typed App",
        )

    def test_hidden_questions_are_never_shown(self, session: Session) -> None:
        """S17: the `when: false` question reaches the prompt but is not shown."""
        hidden = [p.name for p in session.prompts if not p.shown]

        assert hidden == ["package_name"]

    def test_prompt_defaults_carry_the_descendants_overrides(
        self, session: Session
    ) -> None:
        """S17: service's and app's overrides are the defaults the prompts show."""
        defaults = {
            p.name: p.default
            for p in session.prompts
            if p.name in ("python_version", "license")
        }

        assert defaults == {"python_version": "3.13", "license": "Apache-2.0"}

    def test_folder_name_default_comes_from_the_scratch_destination(
        self, session: Session
    ) -> None:
        """S17: project_name defaults to the pass's temp directory, not the project.

        `{{ _folder_name }}` resolves against the Worker's destination, which
        for the unified pass is a throwaway `tmp...` directory.
        """
        default = next(p.default for p in session.prompts if p.name == "project_name")

        assert str(default).startswith("tmp")
