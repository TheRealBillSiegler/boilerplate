"""Drive Copier's prompts in-process from prompt_toolkit pipe input.

``drive_prompts`` runs a callable on a worker thread whose prompt input is a
pipe and whose output is discarded, so no console is needed. A spy on the
prompt function Copier calls records every question's default and whether it
was shown, and feeds the keystrokes of the answer a scenario wants for it: Enter
to accept the default, or the typed text over a cleared prefill.
"""

import threading
from collections.abc import Callable, Mapping, Sequence
from typing import Any, NamedTuple

import pytest
import questionary
from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import PipeInput, create_pipe_input
from prompt_toolkit.output import DummyOutput

GUARD_SECONDS = 90
CLEAR_PREFILL = "\x15"  # Ctrl-U


class Prompt(NamedTuple):
    """One question as Copier put it to the prompt.

    Attributes:
        name: The question's name.
        default: The default the prompt offered, as the value of its choice.
        shown: Whether the question was shown, rather than skipped by its
            ``when``.
    """

    name: str
    default: object
    shown: bool


class PromptSession[T](NamedTuple):
    """What a driven run did.

    Attributes:
        finished: Whether the run ended within the guard time.
        prompts: Every question put to the prompt, in order.
        result: The run's return value, if it returned.
        error: What the run raised, if it raised.
    """

    finished: bool
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
    """Run `run` with Copier's prompts answered from a pipe.

    Args:
        run: The work that prompts, such as an interactive layer update.
        typed: Text to type for a question, keyed by name, over a cleared
            prefill; every other shown question gets Enter, its default.

    Returns:
        What the run did and every question put to the prompt.
    """
    keystrokes = dict(typed or {})
    prompts: list[Prompt] = []
    pipes: list[PipeInput] = []
    outcome: list[T] = []
    errors: list[BaseException] = []
    real = questionary.unsafe_prompt

    def spy(
        questions: Sequence[Mapping[str, Any]],
        answers: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        given = dict(answers or {})
        for question in questions:
            when = question.get("when", True)
            shown = bool(when(given)) if callable(when) else bool(when)
            name = str(question["name"])
            prompts.append(Prompt(name, _plain(question.get("default")), shown))
            if shown:
                text = CLEAR_PREFILL + keystrokes[name] if name in keystrokes else ""
                pipes[0].send_text(text + "\r")
        return real(questions, answers=answers)

    def work() -> None:
        try:
            with (
                create_pipe_input() as pipe,
                create_app_session(input=pipe, output=DummyOutput()),
            ):
                pipes.append(pipe)
                outcome.append(run())
        except BaseException as error:
            errors.append(error)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr("copier._main.unsafe_prompt", spy)
        thread = threading.Thread(target=work, daemon=True)
        thread.start()
        thread.join(timeout=GUARD_SECONDS)
    return PromptSession(
        not thread.is_alive(),
        prompts,
        outcome[0] if outcome else None,
        errors[0] if errors else None,
    )
