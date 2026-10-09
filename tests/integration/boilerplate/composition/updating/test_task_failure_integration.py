"""The task that failed in a run, and what the caller chose to do about it.

Design 04 §Safe Update: a task that fails after the copy back is handed to the
caller, which keeps the updated files or returns the checkout to its starting
commit; a kept failure is reported once the run has recorded itself.
"""

import subprocess
from pathlib import Path

import pytest

from boilerplate.common.exceptions import UpdateTaskFailedError
from boilerplate.composition.updating.failed_task import FailedTask
from boilerplate.composition.updating.task_failure import TaskFailure
from boilerplate.composition.updating.task_failure_choice import TaskFailureChoice
from boilerplate.integrations.copier_types import TaskError
from tests.boilerplate.templates.conftest import commit_all, git, init_repo


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Return a clean git project with one committed file."""
    root = tmp_path / "project"
    root.mkdir()
    init_repo(root)
    (root / "tracked.txt").write_text("start\n", encoding="utf-8")
    commit_all(root, "initial")
    return root


def head(project: Path) -> str:
    return git(project, "rev-parse", "HEAD").strip()


def failing_task() -> None:
    raise TaskError.from_process(subprocess.CompletedProcess("make test", 2))


def passing_task() -> None:
    return None


def keep(_failed: FailedTask) -> TaskFailureChoice:
    return TaskFailureChoice.KEEP


def undo(_failed: FailedTask) -> TaskFailureChoice:
    return TaskFailureChoice.UNDO


class TestRun:
    def test_a_passing_task_keeps_the_files_and_records_no_failure(
        self, project: Path
    ) -> None:
        """Report the files kept and nothing failed when the task passes."""
        failure = TaskFailure(keep)

        kept = failure.run(passing_task, project=project, start_commit=head(project))

        assert (kept, failure.failed) == (True, None)

    def test_a_failed_task_the_caller_keeps_is_recorded(self, project: Path) -> None:
        """Keep the files and remember the task, so the run reports it at the end."""
        failure = TaskFailure(keep)

        kept = failure.run(failing_task, project=project, start_commit=head(project))

        assert (kept, failure.failed) == (
            True,
            FailedTask(
                command="make test",
                returncode=2,
                rerun="Run it by hand from the project root: make test",
            ),
        )

    def test_a_failed_task_the_caller_undoes_restores_the_checkout(
        self, project: Path
    ) -> None:
        """Return tracked files to the starting commit and remove the run's new ones."""
        start = head(project)
        (project / "tracked.txt").write_text("changed by the run\n", encoding="utf-8")
        (project / "added.txt").write_text("added by the run\n", encoding="utf-8")
        failure = TaskFailure(undo)

        kept = failure.run(failing_task, project=project, start_commit=start)

        assert (kept, failure.failed, git(project, "status", "--porcelain")) == (
            False,
            None,
            "",
        )

    def test_an_error_that_is_not_a_task_failure_propagates(
        self, project: Path
    ) -> None:
        """Let a crash in the task runner surface instead of passing as a task."""

        def crash() -> None:
            raise RuntimeError("runner crashed")

        failure = TaskFailure(keep)

        with pytest.raises(RuntimeError, match="runner crashed"):
            failure.run(crash, project=project, start_commit=head(project))


class TestRaiseIfFailed:
    def test_raises_the_task_failure_with_its_message_and_rerun(
        self, project: Path
    ) -> None:
        """Name the task and how to run it by hand, in the caller's words."""
        failure = TaskFailure(keep)
        failure.run(failing_task, project=project, start_commit=head(project))

        with pytest.raises(UpdateTaskFailedError) as raised:
            failure.raise_if_failed(lambda failed: f"{failed.command} failed")

        assert (str(raised.value), raised.value.task, raised.value.remediation) == (
            "make test failed",
            "make test",
            "Run it by hand from the project root: make test",
        )

    def test_does_nothing_when_no_task_failed(self, project: Path) -> None:
        """Stay quiet for a run whose tasks passed."""
        failure = TaskFailure(keep)
        failure.run(passing_task, project=project, start_commit=head(project))

        failure.raise_if_failed(lambda failed: failed.command)
