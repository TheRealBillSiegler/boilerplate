"""Guard tests for the copier-internals import shim.

The module-level import below is itself the primary guard: if a copier upgrade
relocates the private ``Template`` or ``Worker`` symbols the shim re-exports,
collection fails loudly here during CI rather than at render time for a user.
"""

from __future__ import annotations

import dataclasses
import inspect
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
from copier._main import _operation  # pyright: ignore[reportPrivateUsage]
from copier._types import Phase

from boilerplate.integrations.copier_types import (
    MISSING,
    NEW_COPY_DIR_PREFIX,
    OLD_COPY_DIR_PREFIX,
    AnswersMap,
    CopierOperation,
    Question,
    SandboxedEnvironment,
    TaskError,
    Template,
    Worker,
    copier_operation,
    load_answersfile_data,
    tasks_phase,
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


class TestCopierOperation:
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

    @pytest.mark.parametrize("operation", ["copy", "update"])
    def test_operation_is_set_inside_the_block_and_unset_after(
        self, operation: CopierOperation
    ) -> None:
        """Set the named operation for the block, then restore the unset variable."""
        with copier_operation(operation):
            inside = _operation.get()

        assert inside == operation
        with pytest.raises(LookupError):
            _operation.get()

    @pytest.mark.parametrize("operation", ["copy", "update"])
    def test_operation_is_restored_when_the_block_raises(
        self, operation: CopierOperation
    ) -> None:
        """Reset the variable on the way out of a failure too."""
        with pytest.raises(RuntimeError), copier_operation(operation):
            raise RuntimeError("boom")

        with pytest.raises(LookupError):
            _operation.get()


class TestTasksPhase:
    """The shim enters the phase Copier's own task run sets around it."""

    def test_only_run_copy_sets_the_tasks_phase(self) -> None:
        """Pin that ``_execute_tasks`` leaves the phase to its caller."""
        setters = sorted(
            name
            for name in ("run_copy", "run_recopy", "run_update", "_execute_tasks")
            if "Phase.use(Phase.TASKS)" in inspect.getsource(getattr(Worker, name))
        )

        assert setters == ["run_copy"]

    def test_phase_is_tasks_inside_the_block_and_restored_after(self) -> None:
        """Set ``tasks`` for the block, then restore the undefined phase."""
        with tasks_phase():
            inside = Phase.current()

        assert (inside, Phase.current()) == (Phase.TASKS, Phase.UNDEFINED)

    def test_phase_is_restored_when_the_block_raises(self) -> None:
        """Reset the phase on the way out of a failure too."""
        with pytest.raises(RuntimeError), tasks_phase():
            raise RuntimeError("boom")

        assert Phase.current() == Phase.UNDEFINED


class TestTaskError:
    """The shim re-exports the error Copier raises when a task exits non-zero."""

    def test_carries_the_command_and_the_exit_status(self) -> None:
        """Expose ``cmd`` and ``returncode`` of the failed process."""
        process = subprocess.CompletedProcess(["make", "test"], 2, b"", b"")

        error = TaskError.from_process(process)

        assert (error.cmd, error.returncode) == (["make", "test"], 2)


def _required(callable_: Callable[..., object]) -> list[str]:
    """Return the names of the parameters after `self` that have no default."""
    parameters = list(inspect.signature(callable_).parameters.values())[1:]
    return [
        p.name
        for p in parameters
        if p.default is inspect.Parameter.empty
        and p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)
    ]


class TestWorkerInternalsBoilerplateCalls:
    """The Worker members ``ScopedWorker`` and the compose pass call or override."""

    @pytest.mark.parametrize("name", ["_ask", "_render_context", "_external_data"])
    def test_the_member_takes_no_arguments(self, name: str) -> None:
        """``ScopedWorker`` calls each with none, and overrides ``_ask`` the same."""
        assert _required(getattr(Worker, name)) == []

    def test_execute_tasks_takes_the_task_list_alone(self) -> None:
        """The post-walk task run passes the template's tasks as its one argument."""
        assert _required(Worker._execute_tasks) == ["tasks"]  # pyright: ignore[reportPrivateUsage]

    def test_cleanup_hooks_is_an_instance_list(self, tmp_path: Path) -> None:
        """``ScopedWorker`` appends the template's ``_cleanup`` to it."""
        worker = Worker(src_path=str(tmp_path), dst_path=tmp_path / "project")

        assert isinstance(worker._cleanup_hooks, list)  # pyright: ignore[reportPrivateUsage]

    def test_the_fields_the_worker_is_built_with_exist(self) -> None:
        """Compose builds a Worker with each of these keyword arguments."""
        names = {field.name for field in dataclasses.fields(Worker)}

        assert {
            "src_path",
            "dst_path",
            "data",
            "user_defaults",
            "unsafe",
            "overwrite",
            "defaults",
            "skip_tasks",
            "quiet",
            "exclude",
        } <= names


class TestTemplateCleanup:
    """``Template._cleanup`` is what removes a clone, and is safe to call bare."""

    def test_cleanup_takes_no_arguments(self) -> None:
        assert _required(Template._cleanup) == []  # pyright: ignore[reportPrivateUsage]


class TestAnswersMapAndQuestionShape:
    """``check_recorded_answers`` builds both the way ``Worker._ask`` does."""

    def test_answers_map_takes_the_keyword_arguments_boilerplate_passes(self) -> None:
        names = {field.name for field in dataclasses.fields(AnswersMap)}

        assert {"user_defaults", "init", "last", "metadata", "external"} <= names

    def test_answers_map_exposes_the_answer_views_boilerplate_reads(self) -> None:
        members = {field.name for field in dataclasses.fields(AnswersMap)} | set(
            dir(AnswersMap)
        )

        assert {"user", "metadata", "hidden", "last", "init"} <= members

    def test_question_takes_the_keyword_arguments_boilerplate_passes(self) -> None:
        names = {field.name for field in dataclasses.fields(Question)}

        assert {"answers", "context", "jinja_env", "settings", "var_name"} <= names

    @pytest.mark.parametrize("name", ["get_when", "parse_answer", "validate_answer"])
    def test_question_has_the_method(self, name: str) -> None:
        assert callable(getattr(Question, name))
