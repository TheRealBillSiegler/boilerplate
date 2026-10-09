"""Tests for the per-question ``when`` walk in hidden_questions.py.

Design 04 §Safe Update: a question is hidden when its ``when`` evaluates false
under the answers, and a ``when`` that reads a key no file records leaves the
question not hidden. Copier's ``Worker._ask`` gives a hidden question its
default for the questions after it.
"""

from boilerplate.composition.updating.hidden_questions import hidden_questions


class TestALiteralWhen:
    def test_when_false_hides_the_question(self) -> None:
        assert hidden_questions({"slug": {"when": False}}, {}) == {"slug"}

    def test_when_true_does_not(self) -> None:
        assert hidden_questions({"name": {"when": True}}, {}) == set()

    def test_a_question_with_no_when_is_not_hidden(self) -> None:
        assert hidden_questions({"name": {}, "port": "8000"}, {}) == set()

    def test_a_directive_is_not_a_question(self) -> None:
        assert hidden_questions({"_skip": {"when": False}}, {}) == set()


class TestAnExpressionWhen:
    def test_false_under_the_answers_hides_the_question(self) -> None:
        questions = {"use_db": {"type": "bool"}, "db_url": {"when": "{{ use_db }}"}}

        assert hidden_questions(questions, {"use_db": False}) == {"db_url"}

    def test_true_under_the_answers_does_not(self) -> None:
        questions = {"use_db": {"type": "bool"}, "db_url": {"when": "{{ use_db }}"}}

        assert hidden_questions(questions, {"use_db": True}) == set()

    def test_reading_a_question_the_answers_lack_leaves_it_not_hidden(self) -> None:
        """Rendered leniently, the missing `use_db` would read as false."""
        questions = {"use_db": {"type": "bool"}, "db_url": {"when": "{{ use_db }}"}}

        assert hidden_questions(questions, {}) == set()

    def test_copiers_default_filters_render(self) -> None:
        """Copier loads the Ansible filters for every template, `bool` among them."""
        questions = {"flag": {}, "db_url": {"when": "{{ flag | bool }}"}}

        assert hidden_questions(questions, {"flag": "no"}) == {"db_url"}

    def test_a_when_that_cannot_render_leaves_it_not_hidden(self) -> None:
        """Copier reports the unknown filter itself when it asks."""
        questions = {"flag": {}, "db_url": {"when": "{{ flag | no_such_filter }}"}}

        assert hidden_questions(questions, {"flag": False}) == set()


class TestAHiddenQuestionsDefault:
    def test_a_later_when_reads_it(self) -> None:
        questions = {
            "has_db": {"type": "bool", "default": False, "when": False},
            "db_url": {"when": "{{ has_db }}"},
        }

        assert hidden_questions(questions, {}) == {"has_db", "db_url"}

    def test_it_replaces_the_answer_given_for_it(self) -> None:
        """Copier drops a hidden question's recorded answer for its default."""
        questions = {
            "has_db": {"type": "bool", "default": False, "when": False},
            "db_url": {"when": "{{ has_db }}"},
        }

        assert hidden_questions(questions, {"has_db": True}) == {"has_db", "db_url"}
