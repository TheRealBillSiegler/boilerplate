"""Keeping the files of a run whose task failed, or undoing the run.

Design 04 §Safe Update: a failed task is handed to the caller, which keeps the
files or returns the checkout to its starting commit.
"""

from pathlib import Path

import pytest

from boilerplate.composition.updating.failed_task import FailedTask
from boilerplate.composition.updating.keep_or_undo import keep_or_undo
from boilerplate.composition.updating.task_failure_choice import TaskFailureChoice
from tests.boilerplate.templates.conftest import commit_all, git, init_repo

FAILED = FailedTask(command="make", returncode=1, rerun="Run it by hand: make")


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


class TestKeepOrUndo:
    def test_keeping_leaves_the_checkout_as_the_run_left_it(
        self, project: Path
    ) -> None:
        """Report the files kept and touch nothing when the caller keeps them."""
        (project / "added.txt").write_text("added\n", encoding="utf-8")

        kept = keep_or_undo(
            project, head(project), FAILED, lambda _failed: TaskFailureChoice.KEEP
        )

        assert (kept, (project / "added.txt").is_file()) == (True, True)

    def test_undoing_returns_the_checkout_to_the_starting_commit(
        self, project: Path
    ) -> None:
        """Restore the tracked file and remove the file the run added."""
        start = head(project)
        (project / "tracked.txt").write_text("changed\n", encoding="utf-8")
        (project / "added.txt").write_text("added\n", encoding="utf-8")

        kept = keep_or_undo(
            project, start, FAILED, lambda _failed: TaskFailureChoice.UNDO
        )

        assert (kept, git(project, "status", "--porcelain")) == (False, "")

    def test_a_file_made_while_the_caller_decides_survives_an_undo(
        self, project: Path
    ) -> None:
        """List the run's files before asking, so a wait at a prompt costs nothing."""
        start = head(project)

        def decide(_failed: FailedTask) -> TaskFailureChoice:
            (project / "user-notes.txt").write_text("mine\n", encoding="utf-8")
            return TaskFailureChoice.UNDO

        keep_or_undo(project, start, FAILED, decide)

        assert (project / "user-notes.txt").is_file()
