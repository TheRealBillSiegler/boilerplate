"""The failed task a task-failure handler is shown."""

import subprocess

from boilerplate.composition.updating.failed_task import FailedTask
from boilerplate.composition.updating.task_failure_choice import TaskFailureChoice
from boilerplate.composition.updating.task_failure_handler import keep_files
from boilerplate.integrations.copier_types import TaskError


class TestFailedTask:
    def test_names_a_shell_task_as_written(self) -> None:
        """Keep a string command whole."""
        error = TaskError.from_process(subprocess.CompletedProcess("make test", 2))

        failed = FailedTask.from_error(error)

        assert (failed.command, failed.returncode) == ("make test", 2)

    def test_quotes_an_argv_task_so_it_can_be_pasted(self) -> None:
        """Join an argument list the way a shell reads it back."""
        error = TaskError.from_process(
            subprocess.CompletedProcess(["python", "-c", "print('a b')"], 1)
        )

        assert (
            FailedTask.from_error(error).command
            == "python -c 'print('\"'\"'a b'\"'\"')'"
        )

    def test_says_how_to_rerun_the_task(self) -> None:
        """Point at the command and the project root."""
        error = TaskError.from_process(subprocess.CompletedProcess("make", 1))

        assert FailedTask.from_error(error).rerun == (
            "Run it by hand from the project root: make"
        )


class TestKeepFiles:
    def test_a_caller_that_cannot_ask_keeps_the_files(self) -> None:
        """Make keeping the default choice, as ``--non-interactive`` does."""
        failed = FailedTask(command="make", returncode=1, rerun="")

        assert keep_files(failed) is TaskFailureChoice.KEEP
