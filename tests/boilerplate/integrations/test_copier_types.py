"""Guard tests for the copier-internals import shim.

The module-level import below is itself the primary guard: if a copier upgrade
relocates the private ``Template`` or ``Worker`` symbols the shim re-exports,
collection fails loudly here during CI rather than at render time for a user.
"""

from __future__ import annotations

import inspect
from pathlib import Path

from boilerplate.integrations.copier_types import (
    MISSING,
    NEW_COPY_DIR_PREFIX,
    OLD_COPY_DIR_PREFIX,
    AnswersMap,
    Question,
    SandboxedEnvironment,
    Template,
    Worker,
    load_answersfile_data,
    template_public_attr_names,
)


class TestCopierTypesShim:
    """The shim re-exports the copier internals boilerplate depends on."""

    def test_template_is_a_class(self) -> None:
        assert inspect.isclass(Template)

    def test_worker_is_a_class(self) -> None:
        assert inspect.isclass(Worker)

    def test_symbols_originate_from_copier(self) -> None:
        assert Template.__module__.startswith("copier")
        assert Worker.__module__.startswith("copier")

    def test_question_and_answers_map_are_the_classes_a_worker_asks_with(
        self,
    ) -> None:
        """Re-export the pair Worker._ask builds, to validate an answer as it does."""
        assert (Question.__module__, AnswersMap.__module__) == (
            "copier._user_data",
            "copier._user_data",
        )

    def test_sandboxed_environment_is_the_class_a_question_renders_with(
        self,
    ) -> None:
        """Re-export Copier's sandbox; ``Question`` refuses Jinja's own class."""
        assert SandboxedEnvironment.__module__ == "copier._jinja_ext"

    def test_template_public_attr_names_reflects_public_fields(self) -> None:
        names = template_public_attr_names(Template)
        assert "questions_data" in names
        assert "migration_tasks" not in names  # method: callable, excluded
        assert not any(n.startswith("_") for n in names)

    def test_init_only_dataclass_fields_included(self) -> None:
        # Regression: fields with no class-level default (e.g. ``url``) are
        # invisible to dir(cls) and were silently dropped from extracted
        # configs and the merger's layer-local set.
        assert "url" in template_public_attr_names(Template)


class TestLoadAnswersfileData:
    """The shim re-exports Copier's answers-file reader with the shape we rely on."""

    def test_missing_file_reads_as_an_empty_dict(self, tmp_path: Path) -> None:
        assert load_answersfile_data(tmp_path, ".copier-answers.absent.yml") == {}

    def test_present_file_reads_as_its_mapping(self, tmp_path: Path) -> None:
        (tmp_path / ".copier-answers.x.yml").write_text(
            "_commit: v1\nname: demo\n", encoding="utf-8"
        )

        assert load_answersfile_data(tmp_path, ".copier-answers.x.yml") == {
            "_commit": "v1",
            "name": "demo",
        }


class TestUpdateCopyPrefixes:
    """The shim names the temp-directory prefixes Copier's update renders under."""

    def test_prefixes_are_the_ones_the_update_names_its_temp_directories_by(
        self,
    ) -> None:
        """Match the f-string prefixes in ``Worker._apply_update``'s source."""
        source = inspect.getsource(Worker._apply_update)  # pyright: ignore[reportPrivateUsage]
        module = Worker.__module__

        assert (
            'prefix=f"{__name__}.old_copy."' in source,
            'prefix=f"{__name__}.new_copy."' in source,
            OLD_COPY_DIR_PREFIX,
            NEW_COPY_DIR_PREFIX,
        ) == (True, True, f"{module}.old_copy.", f"{module}.new_copy.")


class TestQuestionWithoutADefault:
    """The scoped worker's answer walk tells a missing default by Copier's sentinel."""

    def test_get_default_returns_the_reexported_sentinel(self) -> None:
        """Pin that the shim's MISSING is the object Copier's get_default returns."""
        question = Question(
            var_name="bare",
            answers=AnswersMap(),
            context={},
            jinja_env=SandboxedEnvironment(),
        )

        assert question.get_default() is MISSING
