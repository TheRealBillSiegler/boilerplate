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

        assert set(required_answer_keys(view)) == {"project_name"}

    def test_a_shorthand_question_is_required(self) -> None:
        assert set(required_answer_keys(_view(port="8000"))) == {"port"}

    def test_a_secret_question_is_not(self) -> None:
        assert set(required_answer_keys(_view(api_token={"secret": True}))) == set()

    def test_a_question_the_secret_questions_directive_names_is_not(self) -> None:
        """Copier records no answer for a name `_secret_questions` lists."""
        view = LayerView(
            {"name": {}, "api_token": {}}, (), secret_questions=frozenset({"api_token"})
        )

        assert set(required_answer_keys(view)) == {"name"}

    def test_a_derived_question_is_not(self) -> None:
        view = _view(package_name={"default": "{{ x }}", "when": False})

        assert set(required_answer_keys(view)) == set()

    def test_a_question_that_is_always_asked_is_required(self) -> None:
        assert set(required_answer_keys(_view(a={"when": True}))) == {"a"}

    def test_a_conditional_question_is_not(self) -> None:
        """Copier records no answer for a question its condition hides."""
        assert set(required_answer_keys(_view(a={"when": "{{ use_tests }}"}))) == set()

    def test_a_directive_is_not_a_question(self) -> None:
        assert set(required_answer_keys(_view(_answers_file=".x.yml"))) == set()


class TestCheckAnswersComplete:
    """A trimmed answers file stops the update before any layer runs."""

    def test_passes_when_every_required_key_is_recorded(self) -> None:
        views = {"service": _view(project_name={}, port={})}

        check_answers_complete(views, {"service": {"project_name", "port"}})

    def test_keys_beyond_the_view_are_ignored(self) -> None:
        views = {"service": _view(port={})}

        check_answers_complete(views, {"service": {"port", "stale", "_commit"}})

    def test_names_the_layer_and_the_missing_keys(self) -> None:
        views = {"service": _view(project_name={}, port={}, author_name={})}

        with pytest.raises(AnswersFileIncompleteError) as caught:
            check_answers_complete(views, {"service": {"port"}})

        assert caught.value.error_code == "BP_UPDATE_ANSWERS_INCOMPLETE"
        assert caught.value.missing == {"service": ("project_name", "author_name")}
        assert "service" in str(caught.value)
        assert "project_name" in str(caught.value)
        assert "author_name" in str(caught.value)

    def test_lists_every_incomplete_layer_in_walk_order(self) -> None:
        views = {"core": _view(a={}), "service": _view(a={}, b={}), "app": _view(a={})}

        with pytest.raises(AnswersFileIncompleteError) as caught:
            check_answers_complete(
                views, {"core": {"a"}, "service": {"b"}, "app": set()}
            )

        assert caught.value.missing == {"service": ("a",), "app": ("a",)}

    def test_a_layer_with_no_answers_file_is_missing_every_key(self) -> None:
        with pytest.raises(AnswersFileIncompleteError) as caught:
            check_answers_complete({"service": _view(a={}, b={})}, {})

        assert caught.value.missing == {"service": ("a", "b")}

    def test_a_secret_or_derived_key_is_not_reported(self) -> None:
        views = {"service": _view(a={}, token={"secret": True}, slug={"when": False})}

        with pytest.raises(AnswersFileIncompleteError) as caught:
            check_answers_complete(views, {"service": set()})

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
            self._service(), {"core": {"project_name"}, "service": {"port"}}
        )

    def test_a_key_no_layer_records_stops(self) -> None:
        with pytest.raises(AnswersFileIncompleteError) as caught:
            check_answers_complete(
                self._service(), {"core": set(), "service": {"port"}}
            )

        assert caught.value.missing == {"service": ("project_name",)}

    def test_another_layers_file_does_not_count(self) -> None:
        """Only the declaring layer's record fills a key, never a sibling's copy."""
        with pytest.raises(AnswersFileIncompleteError) as caught:
            check_answers_complete(
                self._service(), {"docs": {"project_name"}, "service": {"port"}}
            )

        assert caught.value.missing == {"service": ("project_name",)}
