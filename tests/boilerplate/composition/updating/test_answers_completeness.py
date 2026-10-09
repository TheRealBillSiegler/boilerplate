"""Tests for the answers-file completeness check in answers_completeness.py."""

import pytest

from boilerplate.common.exceptions import AnswersFileIncompleteError
from boilerplate.composition.updating import (
    check_answers_complete,
    required_answer_keys,
)
from boilerplate.composition.views import LayerView


def _view(**questions: object) -> LayerView:
    return LayerView(questions, ())


class TestRequiredAnswerKeys:
    """Only questions a layer's answers file records are required of it."""

    def test_a_plain_question_is_required(self) -> None:
        view = _view(project_name={"type": "str", "default": "x"})

        assert set(required_answer_keys(view, {})) == {"project_name"}

    def test_a_shorthand_question_is_required(self) -> None:
        assert set(required_answer_keys(_view(port="8000"), {})) == {"port"}

    def test_a_secret_question_is_not(self) -> None:
        assert set(required_answer_keys(_view(api_token={"secret": True}), {})) == set()

    def test_a_question_the_secret_questions_directive_names_is_not(self) -> None:
        """Copier records no answer for a name `_secret_questions` lists."""
        view = LayerView(
            {"name": {}, "api_token": {}}, (), secret_questions=frozenset({"api_token"})
        )

        assert set(required_answer_keys(view, {})) == {"name"}

    def test_a_derived_question_is_not(self) -> None:
        view = _view(package_name={"default": "{{ x }}", "when": False})

        assert set(required_answer_keys(view, {})) == set()

    def test_a_question_that_is_always_asked_is_required(self) -> None:
        assert set(required_answer_keys(_view(a={"when": True}), {})) == {"a"}

    def test_a_question_its_when_hides_is_not(self) -> None:
        """Copier records no answer for a question its condition hides."""
        view = _view(a={"when": "{{ use_tests }}"})

        assert set(required_answer_keys(view, {"use_tests": False})) == set()

    def test_a_question_its_when_shows_is_required(self) -> None:
        view = _view(a={"when": "{{ use_tests }}"})

        assert set(required_answer_keys(view, {"use_tests": True})) == {"a"}

    def test_a_directive_is_not_a_question(self) -> None:
        assert set(required_answer_keys(_view(_answers_file=".x.yml"), {})) == set()


class TestCheckAnswersComplete:
    """A trimmed answers file stops the update before any layer runs."""

    def test_passes_when_every_required_key_is_recorded(self) -> None:
        views = {"service": _view(project_name={}, port={})}

        check_answers_complete(views, {"service": {"project_name": "x", "port": 1}})

    def test_keys_beyond_the_view_are_ignored(self) -> None:
        views = {"service": _view(port={})}

        check_answers_complete(
            views, {"service": {"port": 1, "stale": 2, "_commit": "1.0.0"}}
        )

    def test_names_the_layer_and_the_missing_keys(self) -> None:
        views = {"service": _view(project_name={}, port={}, author_name={})}

        with pytest.raises(AnswersFileIncompleteError) as caught:
            check_answers_complete(views, {"service": {"port": 1}})

        assert caught.value.error_code == "BP_UPDATE_ANSWERS_INCOMPLETE"
        assert caught.value.missing == {"service": ("project_name", "author_name")}
        assert "service" in str(caught.value)
        assert "project_name" in str(caught.value)
        assert "author_name" in str(caught.value)

    def test_lists_every_incomplete_layer_in_walk_order(self) -> None:
        views = {"core": _view(a={}), "service": _view(a={}, b={}), "app": _view(a={})}

        with pytest.raises(AnswersFileIncompleteError) as caught:
            check_answers_complete(
                views, {"core": {"a": 1}, "service": {"b": 1}, "app": {}}
            )

        assert caught.value.missing == {"service": ("a",), "app": ("a",)}

    def test_a_layer_with_no_answers_file_is_missing_every_key(self) -> None:
        with pytest.raises(AnswersFileIncompleteError) as caught:
            check_answers_complete({"service": _view(a={}, b={})}, {})

        assert caught.value.missing == {"service": ("a", "b")}

    def test_a_secret_or_derived_key_is_not_reported(self) -> None:
        views = {"service": _view(a={}, token={"secret": True}, slug={"when": False})}

        with pytest.raises(AnswersFileIncompleteError) as caught:
            check_answers_complete(views, {"service": {}})

        assert caught.value.missing == {"service": ("a",)}


class TestTheDeclaringLayersFileCountsToo:
    """Design 04: a key passes when the layer's own or declaring layer's file has it."""

    @staticmethod
    def _service() -> dict[str, LayerView]:
        questions: dict[str, object] = {"project_name": {}, "port": {}}
        declared_by = {"project_name": "core", "port": "service"}
        return {"service": LayerView(questions, (), (), declared_by)}

    def test_a_key_only_the_declaring_layer_records_passes(self) -> None:
        """The walk fills it for the old copy from core's file, so nothing stops."""
        check_answers_complete(
            self._service(), {"core": {"project_name": "x"}, "service": {"port": 1}}
        )

    def test_a_key_no_layer_records_stops(self) -> None:
        with pytest.raises(AnswersFileIncompleteError) as caught:
            check_answers_complete(
                self._service(), {"core": {}, "service": {"port": 1}}
            )

        assert caught.value.missing == {"service": ("project_name",)}

    def test_another_layers_file_does_not_count(self) -> None:
        """Only the declaring layer's record fills a key, never a sibling's copy."""
        with pytest.raises(AnswersFileIncompleteError) as caught:
            check_answers_complete(
                self._service(), {"docs": {"project_name": "x"}, "service": {"port": 1}}
            )

        assert caught.value.missing == {"service": ("project_name",)}


class TestAConditionalQuestion:
    """Design 04: a question is hidden when its `when` is false under the answers.

    The answers are the layer's own file plus, for each question an ancestor
    declares, the declaring ancestor's record; a `when` that reads a key no
    file records leaves the question not hidden.
    """

    @staticmethod
    def _service() -> dict[str, LayerView]:
        """Core declares `db_url`; service overrides it to ask only off SQLite."""
        questions: dict[str, object] = {
            "db_url": {"type": "str", "when": "{{ not use_sqlite }}"},
            "use_sqlite": {"type": "bool"},
        }
        declared_by = {"db_url": "core", "use_sqlite": "service"}
        return {"service": LayerView(questions, (), (), declared_by)}

    def test_a_question_its_when_shows_is_required(self) -> None:
        with pytest.raises(AnswersFileIncompleteError) as caught:
            check_answers_complete(
                self._service(), {"core": {}, "service": {"use_sqlite": False}}
            )

        assert caught.value.missing == {"service": ("db_url",)}

    def test_a_question_its_when_hides_is_not(self) -> None:
        check_answers_complete(
            self._service(), {"core": {}, "service": {"use_sqlite": True}}
        )

    def test_the_declaring_ancestors_record_decides_the_when(self) -> None:
        """The flag service's `when` reads is core's, so core's record counts."""
        questions: dict[str, object] = {
            "use_db": {"type": "bool"},
            "db_url": {"type": "str", "when": "{{ use_db }}"},
        }
        views = {
            "service": LayerView(
                questions, (), (), {"use_db": "core", "db_url": "service"}
            )
        }

        with pytest.raises(AnswersFileIncompleteError) as caught:
            check_answers_complete(
                views, {"core": {"use_db": True}, "service": {"use_db": False}}
            )

        assert caught.value.missing == {"service": ("db_url",)}

    def test_a_when_that_reads_an_unrecorded_key_leaves_the_question_required(
        self,
    ) -> None:
        """Rendered leniently, `{{ use_db }}` would read as false and hide it."""
        views = {
            "service": _view(
                use_db={"type": "bool"}, db_url={"type": "str", "when": "{{ use_db }}"}
            )
        }

        with pytest.raises(AnswersFileIncompleteError) as caught:
            check_answers_complete(views, {"service": {}})

        assert caught.value.missing == {"service": ("use_db", "db_url")}

    def test_a_when_that_reads_a_derived_question_sees_its_default(self) -> None:
        """Copier computes a hidden question's default for every later question."""
        views = {
            "service": _view(
                has_db={"type": "bool", "default": False, "when": False},
                db_url={"type": "str", "when": "{{ has_db }}"},
            )
        }

        check_answers_complete(views, {"service": {}})
