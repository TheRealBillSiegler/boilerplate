"""``worker_session`` turns Copier's prompt failures into Boilerplate's own errors.

The Worker is a stand-in that raises the failure under test: a real Worker
cannot be pushed into a prompt failure or a cancellation on every platform.
"""

from pathlib import Path
from types import TracebackType

import pytest
from copier.errors import CopierAnswersInterrupt

import boilerplate.composition.rendering.worker_session as session_mod
from boilerplate.common.exceptions import (
    InteractiveRenderFailedError,
    UserCancelledError,
)
from boilerplate.composition.rendering.worker_options import WorkerOptions
from boilerplate.composition.rendering.worker_session import worker_session
from boilerplate.composition.views import LayerView


class _PromptToolkitError(Exception):
    """Stand-in for prompt_toolkit.output.win32.NoConsoleScreenBufferError."""


# Pretend this exception lives in prompt_toolkit so the translator recognizes it.
_PromptToolkitError.__module__ = "prompt_toolkit.output.win32"


class _QuestionaryError(Exception):
    """Stand-in for questionary.*Error raised under a pseudo-TTY."""


_QuestionaryError.__module__ = "questionary.prompts.text"


class _UnrelatedError(Exception):
    """Stand-in for a crash that is NOT from the prompt stack."""


def _raising_worker(error: BaseException) -> type:
    """Return a Worker type whose ``run_copy`` raises `error`."""

    class _Worker:
        def __init__(self, **kwargs: object) -> None:
            self.init_kwargs = kwargs

        def __enter__(self) -> "_Worker":
            return self

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            tb: TracebackType | None,
        ) -> bool:
            return False

        def run_copy(self) -> None:
            raise error

    return _Worker


def _render_with(
    monkeypatch: pytest.MonkeyPatch, error: BaseException, tmp_path: Path
) -> None:
    """Run a session whose Worker raises `error` from ``run_copy``."""
    monkeypatch.setattr(session_mod, "ScopedWorker", _raising_worker(error))
    options: WorkerOptions = {"src_path": str(tmp_path), "dst_path": tmp_path / "out"}
    with worker_session(options, LayerView({}, ())) as worker:
        worker.run_copy()


class TestInteractivePromptCrashTranslation:
    """Worker errors originating in prompt_toolkit/questionary get translated."""

    @pytest.mark.parametrize(
        "error",
        [_PromptToolkitError("simulated"), _QuestionaryError("simulated")],
        ids=["prompt_toolkit", "questionary"],
    )
    def test_prompt_stack_error_is_translated_and_stays_the_cause(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: Exception
    ) -> None:
        with pytest.raises(InteractiveRenderFailedError) as exc_info:
            _render_with(monkeypatch, error, tmp_path)

        assert exc_info.value.__cause__ is error

    def test_unrelated_error_is_not_translated(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Errors not from prompt_toolkit/questionary propagate unchanged."""
        with pytest.raises(_UnrelatedError):
            _render_with(monkeypatch, _UnrelatedError("unrelated bug"), tmp_path)


class TestUserCancellationTranslation:
    """Ctrl+C at a prompt is recognized as user cancellation, not a crash."""

    def test_copier_answers_interrupt_becomes_concise_cancellation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The translated message never carries the interrupt's payload.

        Regression test: the payload holds the answers, the question and the
        template path, which may be large or sensitive.
        """
        interrupt = CopierAnswersInterrupt(
            "AnswersMap(fake answers)",  # pyright: ignore[reportArgumentType]
            "Question(fake question)",  # pyright: ignore[reportArgumentType]
            f"Template(path={tmp_path.resolve()})",  # pyright: ignore[reportArgumentType]
        )

        with pytest.raises(UserCancelledError) as exc_info:
            _render_with(monkeypatch, interrupt, tmp_path)

        assert str(exc_info.value) == "Aborted."

    def test_plain_keyboard_interrupt_outside_prompt_is_not_swallowed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A bare KeyboardInterrupt (not CopierAnswersInterrupt) propagates.

        Only CopierAnswersInterrupt gets the friendly cancellation treatment. A
        plain Ctrl+C elsewhere in the render path (a file write, say) is a less
        controlled situation and must not be caught or reclassified.
        """
        with pytest.raises(KeyboardInterrupt):
            _render_with(monkeypatch, KeyboardInterrupt(), tmp_path)


class TestRecordedAnswerCheck:
    """A compose session supplies every answer as data, so it checks no recorded one."""

    def test_the_worker_is_built_with_the_recorded_answer_check_off(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(session_mod, "ScopedWorker", _raising_worker(KeyError()))
        options: WorkerOptions = {
            "src_path": str(tmp_path),
            "dst_path": tmp_path / "out",
        }

        with worker_session(options, LayerView({}, ())) as worker:
            built_with = worker.init_kwargs  # pyright: ignore[reportAttributeAccessIssue]

        assert built_with["check_recorded"] is False
