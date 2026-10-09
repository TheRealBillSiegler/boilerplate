"""The view choice and answer walk of ``ScopedWorker``, not its renders."""

import contextlib
import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
import yaml

from boilerplate.common.exceptions import RecordedAnswerRejectedError
from boilerplate.composition.updating import ScopedWorker
from boilerplate.composition.views import LayerView
from boilerplate.integrations.copier_types import (
    NEW_COPY_DIR_PREFIX,
    OLD_COPY_DIR_PREFIX,
    AnswersMap,
    Worker,
)

OLD = LayerView({"old_question": {}}, ())
TARGET = LayerView({"new_question": {}}, ())


def _worker(tmp_path: Path, destination: Path) -> ScopedWorker:
    return ScopedWorker(  # pyright: ignore[reportCallIssue]
        src_path=str(tmp_path),
        dst_path=destination,
        old_view=OLD,
        target_view=TARGET,
    )


class TestViewForRender:
    def test_the_old_copy_renders_under_the_old_view(self, tmp_path: Path) -> None:
        worker = _worker(tmp_path, tmp_path / f"{OLD_COPY_DIR_PREFIX}ab12")

        assert worker.view_for_render() == OLD

    @pytest.mark.parametrize(
        "destination",
        ["project", f"{NEW_COPY_DIR_PREFIX}ab12"],
        ids=["in_place", "new_copy"],
    )
    def test_the_other_renders_use_the_target_view(
        self, tmp_path: Path, destination: str
    ) -> None:
        worker = _worker(tmp_path, tmp_path / destination)

        assert worker.view_for_render() == TARGET


def _scoped_worker(
    tmp_path: Path,
    name: str,
    questions: Mapping[str, Any],
    recorded: Mapping[str, Any],
    *,
    data: Mapping[str, Any] | None = None,
    defaults: bool = True,
    skip_answered: bool = False,
) -> ScopedWorker:
    """Build a worker whose project at `tmp_path/name` records `recorded` answers."""
    destination = tmp_path / name
    destination.mkdir()
    (destination / ".copier-answers.yml").write_text(
        yaml.safe_dump({"_src_path": "unused", **recorded}), encoding="utf-8"
    )
    view = LayerView(questions, ())
    return ScopedWorker(  # pyright: ignore[reportCallIssue]
        src_path=str(tmp_path),
        dst_path=destination,
        old_view=view,
        target_view=view,
        layer="demo",
        data=dict(data or {}),
        defaults=defaults,
        skip_answered=skip_answered,
    )


def _walk(
    tmp_path: Path,
    questions: Mapping[str, Any],
    recorded: Mapping[str, Any],
    *,
    data: Mapping[str, Any] | None = None,
    defaults: bool = True,
    skip_answered: bool = False,
) -> AnswersMap:
    """Run the recorded-answer check of `questions` against `recorded` answers.

    Returns:
        The answers the check ended with.
    """
    worker = _scoped_worker(
        tmp_path,
        "project",
        questions,
        recorded,
        data=data,
        defaults=defaults,
        skip_answered=skip_answered,
    )
    worker.check_recorded_answers()
    return worker.answers


# `port` is retyped to int while the project records the str '8000'; `flag` has
# a recorded answer its choices reject and a `when` that reads `port`.
RETYPED_PORT: dict[str, Any] = {
    "port": {"type": "int", "default": 1},
    "flag": {
        "type": "str",
        "choices": ["yes"],
        "default": "yes",
        "when": "{{ port == 8000 }}",
    },
}
RETYPED_PORT_RECORDED = {"port": "8000", "flag": "nope"}


class TestWhenReadsAnAnswerBehindSkipAnswered:
    """Under ``skip_answered`` Copier leaves an answered question as recorded."""

    def test_a_later_when_reads_the_recorded_value_as_it_stands(
        self, tmp_path: Path
    ) -> None:
        """Evaluate `port == 8000` False on the raw '8000', so `flag` is not asked.

        The expected outcome is Copier's: ``Worker._ask`` ends the loop body for
        an answered question before it stores a parsed answer.
        """
        answers = _walk(
            tmp_path, RETYPED_PORT, RETYPED_PORT_RECORDED, skip_answered=True
        )

        assert "flag" in answers.hidden

    def test_a_later_when_reads_the_parsed_answer_otherwise(
        self, tmp_path: Path
    ) -> None:
        """Evaluate `port == 8000` True on the cast int, so `flag` is asked."""
        with pytest.raises(RecordedAnswerRejectedError) as raised:
            _walk(tmp_path, RETYPED_PORT, RETYPED_PORT_RECORDED)

        assert raised.value.question == "flag"


# `gate` has a `when` that cannot render: an unknown filter raises Jinja's own
# error, an undefined name Copier's.
UNCOMPILABLE_WHEN: dict[str, Any] = {
    "gate": {
        "type": "str",
        "choices": ["yes"],
        "default": "yes",
        "when": "{{ 1 | no_such_filter }}",
    },
}
UNDEFINED_WHEN: dict[str, Any] = {
    "gate": {
        "type": "str",
        "choices": ["yes"],
        "default": "yes",
        "when": "{{ undefined_name.attribute }}",
    },
}


class TestWhenThatCannotRender:
    """Copier evaluates a ``when`` before anything else and fails when it cannot."""

    @pytest.mark.parametrize(
        "questions",
        [UNCOMPILABLE_WHEN, UNDEFINED_WHEN],
        ids=["unknown_filter", "undefined_name"],
    )
    @pytest.mark.parametrize(
        ("recorded", "kept"),
        [("nope", False), ("yes", True)],
        ids=["rejected", "accepted"],
    )
    def test_the_template_error_is_left_to_copier(
        self, tmp_path: Path, questions: Mapping[str, Any], recorded: str, kept: bool
    ) -> None:
        """End the walk without a rejection, whatever the recorded answer is.

        The expected outcome is Copier's: ``Worker._ask`` drops a rejected
        answer silently and then fails evaluating the ``when``. The walk ends
        there, so the answer a question accepts is still recorded.
        """
        answers = _walk(tmp_path, questions, {"gate": recorded})

        assert ("gate" in answers.last) is kept


# `b` has a recorded answer that is valid, but a part of its question that
# Copier reads while it validates the answer cannot render.
CHOICES_CANNOT_RENDER: dict[str, Any] = {
    "b": {"type": "str", "choices": "{{ undefined_name.attribute }}", "default": "p"},
}
UNSUPPORTED_TYPE: dict[str, Any] = {"b": {"type": "no_such_type", "default": "p"}}


class TestTemplateErrorBehindARecordedAnswer:
    """Copier reports a question's template error, not a rejection of its answer."""

    @pytest.mark.parametrize(
        "questions",
        [CHOICES_CANNOT_RENDER, UNSUPPORTED_TYPE],
        ids=["choices_cannot_render", "unsupported_type"],
    )
    def test_the_error_is_left_to_copier(
        self, tmp_path: Path, questions: Mapping[str, Any]
    ) -> None:
        """End the walk without a rejection.

        The expected outcome is Copier's: ``Worker._ask`` drops an answer it
        cannot validate silently and then fails rendering the default.
        """
        answers = _walk(tmp_path, questions, {"b": "p"})

        assert "b" not in answers.last

    def test_a_null_recorded_for_a_typed_question_is_rejected(
        self, tmp_path: Path
    ) -> None:
        """Reject a recorded null, which only a json or yaml question can take."""
        with pytest.raises(RecordedAnswerRejectedError) as raised:
            _walk(tmp_path, {"port": {"type": "int", "default": 1}}, {"port": None})

        assert raised.value.question == "port"


# A later question whose recorded answer its choices reject.
LATER_REJECTED: dict[str, Any] = {
    "later": {"type": "str", "choices": ["yes"], "default": "yes"},
}
LATER_RECORDED = {"later": "nope"}

NO_DEFAULT: dict[str, Any] = {"first": {"type": "str"}}
UNRENDERABLE_DEFAULT: dict[str, Any] = {
    "first": {"type": "str", "default": "{{ undefined_name.attribute }}"},
}
HIDDEN_UNRENDERABLE_DEFAULT: dict[str, Any] = {
    "first": {
        "type": "str",
        "when": False,
        "default": "{{ undefined_name.attribute }}",
    },
}


class TestWalkStopsWhereCopierFails:
    """With defaults set, Copier fails at the first asked question it cannot default."""

    def test_a_later_rejected_answer_is_not_reported(self, tmp_path: Path) -> None:
        """Leave `later` recorded, as the walk never reaches it."""
        answers = _walk(tmp_path, {**NO_DEFAULT, **LATER_REJECTED}, LATER_RECORDED)

        assert answers.last["later"] == "nope"

    @pytest.mark.parametrize(
        "first",
        [UNRENDERABLE_DEFAULT, HIDDEN_UNRENDERABLE_DEFAULT],
        ids=["asked", "hidden"],
    )
    @pytest.mark.parametrize("defaults", [True, False], ids=["defaults", "prompted"])
    def test_a_default_that_cannot_render_ends_the_walk_in_every_mode(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
        first: Mapping[str, Any],
        defaults: bool,
    ) -> None:
        """Report nothing about `later`, asked or hidden, prompted or not.

        The expected outcome is Copier's: ``Worker._ask`` computes the default
        of a hidden question, and of an asked one before it prompts, and fails
        on a default that cannot render.
        """
        with caplog.at_level(logging.WARNING):
            _walk(
                tmp_path,
                {**first, **LATER_REJECTED},
                LATER_RECORDED,
                defaults=defaults,
            )

        assert "'later' is rejected" not in caplog.text

    def test_an_interactive_step_walks_on(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Let the prompt ask `first`, and still warn about `later`."""
        with caplog.at_level(logging.WARNING):
            _walk(
                tmp_path,
                {**NO_DEFAULT, **LATER_REJECTED},
                LATER_RECORDED,
                defaults=False,
            )

        assert "'later' is rejected" in caplog.text


# `b`'s default is the earlier answer `a`, which its validator refuses for 'x'.
DEFAULT_REFUSED_BY_VALIDATOR: dict[str, Any] = {
    "a": {"type": "str", "default": "x"},
    "b": {
        "type": "str",
        "default": "{{ a }}",
        "validator": "{% if b == 'x' %}no x{% endif %}",
    },
}


class TestDefaultThatFailsItsValidator:
    """The walk fills `a` with its default, which a prompt may replace."""

    @pytest.mark.parametrize("defaults", [True, False], ids=["defaults", "prompted"])
    def test_the_walk_ends_and_leaves_the_error_to_copier(
        self, tmp_path: Path, defaults: bool
    ) -> None:
        """Raise nothing, since a prompted `a` may give `b` a default that passes.

        The expected outcome is Copier's: ``Worker._ask`` prompts `a` before it
        computes `b`'s default, and under defaults fails at `b` with the same
        validation error.
        """
        answers = _walk(tmp_path, DEFAULT_REFUSED_BY_VALIDATOR, {}, defaults=defaults)

        assert dict(answers.user) == {"a": "x"}


# `s` is a secret whose forced value fails its validator; `b` has a recorded
# answer its choices reject.
SECRET_REFUSING_ITS_DATA: dict[str, Any] = {
    "s": {
        "type": "str",
        "secret": True,
        "default": "ok",
        "validator": "{% if s == 'bad' %}bad s{% endif %}",
    },
    "b": {"type": "str", "choices": ["p", "q"], "default": "p"},
}


class TestForcedDataThatFailsItsValidator:
    """Copier validates the data it is passed for every question, secret or not."""

    def test_the_walk_ends_before_a_later_rejected_answer(self, tmp_path: Path) -> None:
        """Report nothing about `b`, since Copier fails first on `s`'s data.

        The expected outcome is Copier's: ``Worker._ask`` parses and validates
        the data for `s` before it reaches `b`, and raises Copier's own error.
        """
        answers = _walk(
            tmp_path, SECRET_REFUSING_ITS_DATA, {"b": "r"}, data={"s": "bad"}
        )

        assert answers.last["b"] == "r"


# Question shapes that exercise each way the walk can diverge from Copier. Each
# entry is (questions, recorded answers, data, skip_answered).
_Shape = tuple[dict[str, Any], dict[str, Any], dict[str, Any], bool]
SHAPES: dict[str, _Shape] = {
    "retyped": (RETYPED_PORT, RETYPED_PORT_RECORDED, {}, False),
    "retyped_skip_answered": (RETYPED_PORT, RETYPED_PORT_RECORDED, {}, True),
    "narrowed_choices": (
        {"b": {"type": "str", "choices": ["x", "y"], "default": "x"}},
        {"b": "z"},
        {},
        False,
    ),
    "when_on_an_added_question": (
        {
            "added": {"type": "int", "default": 1},
            "c": {
                "type": "str",
                "choices": ["yes"],
                "default": "yes",
                "when": "{{ added == 1 }}",
            },
        },
        {"c": "nope"},
        {},
        False,
    ),
    "uncompilable_when": (UNCOMPILABLE_WHEN, {"gate": "nope"}, {}, False),
    "undefined_when": (UNDEFINED_WHEN, {"gate": "yes"}, {}, False),
    "no_default": ({**NO_DEFAULT, **LATER_REJECTED}, LATER_RECORDED, {}, False),
    "unrenderable_default": (
        {**UNRENDERABLE_DEFAULT, **LATER_REJECTED},
        LATER_RECORDED,
        {},
        False,
    ),
    "hidden_unrenderable_default": (
        {**HIDDEN_UNRENDERABLE_DEFAULT, **LATER_REJECTED},
        LATER_RECORDED,
        {},
        False,
    ),
    "default_refused_by_validator": (DEFAULT_REFUSED_BY_VALIDATOR, {}, {}, False),
    "secret_refusing_its_data": (
        SECRET_REFUSING_ITS_DATA,
        {"b": "r"},
        {"s": "bad"},
        False,
    ),
    "hidden_with_a_recorded_answer": (
        {"h": {"type": "str", "when": False, "default": "d"}},
        {"h": "x"},
        {},
        False,
    ),
    "unsupported_type": (UNSUPPORTED_TYPE, {"b": "p"}, {}, False),
    "unchanged": (
        {"b": {"type": "str", "choices": ["p", "q"], "default": "p"}},
        {"b": "q"},
        {},
        False,
    ),
}


class TestWalkAgreesWithCopier:
    """Compare the walk with Copier's own ``Worker._ask`` run under defaults."""

    @pytest.mark.parametrize("shape", SHAPES.values(), ids=SHAPES.keys())
    def test_the_answers_it_ends_with_are_the_answers_copier_has_there(
        self, tmp_path: Path, shape: _Shape
    ) -> None:
        """Match Copier's `user`, `hidden` and `last` where the walk ends.

        Copier is the source of truth: it runs on its own copy of the project,
        and where it fails the answers it holds are the ones at that point.
        Where the walk finds a rejection, Copier must have dropped that
        recorded answer instead.
        """
        questions, recorded, data, skip_answered = shape
        copier = _scoped_worker(
            tmp_path,
            "copier",
            questions,
            recorded,
            data=data,
            skip_answered=skip_answered,
        )
        with contextlib.suppress(Exception):
            Worker._ask(copier)  # pyright: ignore[reportPrivateUsage]

        try:
            walked = _walk(
                tmp_path, questions, recorded, data=data, skip_answered=skip_answered
            )
        except RecordedAnswerRejectedError as rejection:
            assert rejection.question not in copier.answers.last
        else:
            assert (walked.user, walked.hidden, walked.last) == (
                copier.answers.user,
                copier.answers.hidden,
                copier.answers.last,
            )


# Core declares `db_url`; in this layer's view it is asked only for Postgres.
POSTGRES_ONLY: dict[str, Any] = {
    "use_pg": {"type": "bool", "default": False},
    "db_url": {"type": "str", "default": "", "when": "{{ use_pg }}"},
}
CORES_DB_URL = {"db_url": "postgres://core"}


def _old_copy_data(tmp_path: Path, own: Mapping[str, Any]) -> dict[str, Any]:
    """Return the old copy's data for a layer whose own file records `own`."""
    view = LayerView(POSTGRES_ONLY, ())
    worker = ScopedWorker(  # pyright: ignore[reportCallIssue]
        src_path=str(tmp_path),
        dst_path=tmp_path / f"{OLD_COPY_DIR_PREFIX}ab12",
        data=dict(own),
        old_view=view,
        target_view=view,
        old_copy_fill=CORES_DB_URL,
    )
    return worker.old_copy_data()


class TestTheOldCopyFill:
    """Design 04: the fill supplies a key the layer's own file lacks.

    Copier records no answer for a hidden question, and data it is given for
    one still reaches the render, so a question this view hides keeps
    Copier's default instead of the ancestor's record.
    """

    def test_a_question_this_view_shows_is_filled(self, tmp_path: Path) -> None:
        assert _old_copy_data(tmp_path, {"use_pg": True}) == {
            "db_url": "postgres://core",
            "use_pg": True,
        }

    def test_a_question_this_view_hides_is_not(self, tmp_path: Path) -> None:
        assert _old_copy_data(tmp_path, {"use_pg": False}) == {"use_pg": False}

    def test_a_key_the_own_file_records_keeps_its_value(self, tmp_path: Path) -> None:
        own = {"use_pg": True, "db_url": "postgres://own"}

        assert _old_copy_data(tmp_path, own) == own
