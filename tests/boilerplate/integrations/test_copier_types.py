"""Guard tests for the copier-internals import shim.

The module-level import below is itself the primary guard: if a copier upgrade
relocates the private ``Template`` or ``Worker`` symbols the shim re-exports,
collection fails loudly here during CI rather than at render time for a user.
"""

from __future__ import annotations

import inspect
import subprocess
from pathlib import Path

import pytest
from copier._main import _operation  # pyright: ignore[reportPrivateUsage]

from boilerplate.integrations.copier_types import (
    MISSING,
    NEW_COPY_DIR_PREFIX,
    OLD_COPY_DIR_PREFIX,
    AnswersMap,
    Question,
    SandboxedEnvironment,
    TaskError,
    Template,
    Worker,
    copy_operation,
    load_answersfile_data,
    template_public_attr_names,
    update_operation,
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


class TestUpdateOperation:
    """The shim sets the ContextVar Copier's task runner reads its operation from."""

    def test_task_runner_reads_the_operation_from_the_context_variable(self) -> None:
        """Pin the private ContextVar and its reader in Copier's source."""
        source = inspect.getsource(Worker._execute_tasks)  # pyright: ignore[reportPrivateUsage]

        assert "_operation.get()" in source

    def test_only_the_run_methods_set_the_operation(self) -> None:
        """Pin that nothing but ``run_copy``, ``run_recopy`` and ``run_update`` do."""
        setters = sorted(
            name
            for name in ("run_copy", "run_recopy", "run_update", "_execute_tasks")
            if "as_operation" in inspect.getsource(getattr(Worker, name))
        )

        assert setters == ["run_copy", "run_recopy", "run_update"]

    def test_operation_is_update_inside_the_block_and_unset_after(self) -> None:
        """Set ``"update"`` for the block, then restore the unset variable."""
        with update_operation():
            inside = _operation.get()

        assert inside == "update"
        with pytest.raises(LookupError):
            _operation.get()

    def test_operation_is_restored_when_the_block_raises(self) -> None:
        """Reset the variable on the way out of a failure too."""
        with pytest.raises(RuntimeError), update_operation():
            raise RuntimeError("boom")

        with pytest.raises(LookupError):
            _operation.get()


class TestCopyOperation:
    """The shim sets the operation of a task run that follows a copy."""

    def test_operation_is_copy_inside_the_block_and_unset_after(self) -> None:
        """Set ``"copy"`` for the block, then restore the unset variable."""
        with copy_operation():
            inside = _operation.get()

        assert inside == "copy"
        with pytest.raises(LookupError):
            _operation.get()

    def test_operation_is_restored_when_the_block_raises(self) -> None:
        """Reset the variable on the way out of a failure too."""
        with pytest.raises(RuntimeError), copy_operation():
            raise RuntimeError("boom")

        with pytest.raises(LookupError):
            _operation.get()


class TestTaskError:
    """The shim re-exports the error Copier raises when a task exits non-zero."""

    def test_carries_the_command_and_the_exit_status(self) -> None:
        """Expose ``cmd`` and ``returncode`` of the failed process."""
        process = subprocess.CompletedProcess(["make", "test"], 2, b"", b"")

        error = TaskError.from_process(process)

        assert (error.cmd, error.returncode) == (["make", "test"], 2)
