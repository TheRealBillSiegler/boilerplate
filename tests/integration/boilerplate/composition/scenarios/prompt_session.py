"""Drive Copier's prompts in-process from prompt_toolkit pipe input.

``drive_prompts`` runs a callable on the calling thread with prompt input that is
already at end of input and output that is discarded, so no console is needed.
A spy on the prompt function Copier calls records every question's default and
whether it was shown, and answers each call from a fresh pipe holding only the
keystrokes of the answers a scenario wants for that call's shown questions:
Enter to accept the default, or the typed text over a cleared prefill, then end
of input. A rejected answer the prompt would ask again, or a question asked
outside the spy, therefore reads end of input and fails at once, as Copier's
``InteractiveSessionError``, with no clock to wait out.
"""

from collections.abc import Callable, Mapping, Sequence
from typing import Any, NamedTuple

import pytest
import questionary
from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

from tests.integration.boilerplate.composition.scenarios.prompt import Prompt

CLEAR_PREFILL = "\x15"  # Ctrl-U


class PromptSession[T](NamedTuple):
    """What a driven run did.

    Attributes:
        prompts: Every question put to the prompt, in order.
        result: The run's return value, if it returned.
        error: What the run raised, if it raised.
    """

    prompts: list[Prompt]
    result: T | None
    error: BaseException | None

    @property
    def shown(self) -> list[str]:
        """The names of the questions the user was shown, in order."""
        return [p.name for p in self.prompts if p.shown]

    def default_of(self, name: str) -> object:
        """Return the default the prompt for `name` offered."""
        return next(p.default for p in self.prompts if p.name == name)


def _plain(default: object) -> object:
    """Return a choice question's default as the value of its choice."""
    return default.value if isinstance(default, questionary.Choice) else default


def drive_prompts[T](
    run: Callable[[], T], typed: Mapping[str, str] | None = None
) -> PromptSession[T]:
    """Run `run` with Copier's prompts answered from pipes that end after one call.

    Args:
        run: The work that prompts, such as an interactive layer update.
        typed: Text to type for a question, keyed by name, over a cleared
            prefill; every other shown question gets Enter, its default.

    Returns:
        What the run did and every question put to the prompt. An error the
        run raised, including end of input at a prompt that wanted more than
        its keystrokes, is in `error`.
    """
    keystrokes = dict(typed or {})
    prompts: list[Prompt] = []
    real = questionary.unsafe_prompt

    def spy(
        questions: Sequence[Mapping[str, Any]],
        answers: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        given = dict(answers or {})
        keys: list[str] = []
        for question in questions:
            when = question.get("when", True)
            shown = bool(when(given)) if callable(when) else bool(when)
            name = str(question["name"])
            prompts.append(Prompt(name, _plain(question.get("default")), shown))
            if shown:
                text = CLEAR_PREFILL + keystrokes[name] if name in keystrokes else ""
                keys.append(text + "\r")
        with (
            create_pipe_input() as pipe,
            create_app_session(input=pipe, output=DummyOutput()),
        ):
            pipe.send_text("".join(keys))
            pipe.close()
            return real(questions, answers=answers)

    outcome: T | None = None
    error: Exception | None = None
    with (
        pytest.MonkeyPatch.context() as patch,
        create_pipe_input() as closed,
        create_app_session(input=closed, output=DummyOutput()),
    ):
        closed.close()
        patch.setattr("copier._main.unsafe_prompt", spy)
        try:
            outcome = run()
        except Exception as raised:
            error = raised
    return PromptSession(prompts, outcome, error)
