"""Fixtures for the staging tests: a throwaway git project and a temp root."""

from collections.abc import Callable
from pathlib import Path

import pytest

from boilerplate.composition.staging.git_commands import run_git
from boilerplate.integrations.copier_types import ProcessExecutionError
from tests.boilerplate.templates.conftest import commit_all, git, init_repo

PROJECT_NAME = "my-project"
FILES = {"keep.txt": "keep\n", "edit.txt": "one\ntwo\nthree\n", "drop.txt": "drop\n"}


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Return a clean git project named `PROJECT_NAME` with three committed files."""
    root = tmp_path / "work" / PROJECT_NAME
    root.mkdir(parents=True)
    init_repo(root)
    for name, text in FILES.items():
        (root / name).write_text(text, encoding="utf-8", newline="\n")
    commit_all(root, "initial")
    return root


@pytest.fixture
def staging_root(tmp_path: Path) -> Path:
    """Return an empty directory standing in for the system temp directory."""
    root = tmp_path / "system-temp"
    root.mkdir()
    return root


def head(repo: Path) -> str:
    """Return the commit `repo`'s HEAD points at."""
    return git(repo, "rev-parse", "HEAD").strip()


def restore_dying_after_one_file(failure: BaseException) -> Callable[..., str]:
    """Return a git runner whose copy-back restore writes one file, then fails.

    Every other git call, the recovery's own restore included, runs for real.
    """

    def run(cwd: Path, *args: str, stdin: str | None = None) -> str:
        is_copy_back_restore = args[0] == "restore" and "--staged" not in args
        if is_copy_back_restore:
            run_git(cwd, "restore", args[1], "--worktree", "--", "added.txt")
            raise failure
        return run_git(cwd, *args, stdin=stdin)

    return run


def restore_and_undo_dying(undo_failure: BaseException) -> Callable[..., str]:
    """Return a git runner whose copy back fails after one file, then its undo too.

    The copy back's restore writes one file and fails as a full disk does; the
    undo's restore of the starting commit then raises `undo_failure`, so the
    checkout keeps the one file. Every other git call runs for real.
    """
    copy_back = restore_dying_after_one_file(disk_full())

    def run(cwd: Path, *args: str, stdin: str | None = None) -> str:
        if args[0] == "restore" and "--staged" in args:
            raise undo_failure
        return copy_back(cwd, *args, stdin=stdin)

    return run


def disk_full() -> ProcessExecutionError:
    return ProcessExecutionError(["git", "restore"], 128, "", "No space left on device")


def file_in_use() -> ProcessExecutionError:
    return ProcessExecutionError(
        ["git", "restore"], 255, "", "unable to unlink added.txt: Permission denied"
    )
