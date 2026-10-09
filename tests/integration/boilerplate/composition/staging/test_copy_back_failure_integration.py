"""A copy back that fails partway restores the checkout and keeps the worktree."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from boilerplate.common.exceptions import UpdateCopyBackFailedError
from boilerplate.composition.staging import (
    JOURNAL_NAME,
    IntentOperation,
    StagingWorktree,
    remove_stale_staging,
)
from boilerplate.composition.staging.git_commands import (
    run_git,
)
from boilerplate.integrations.copier_types import ProcessExecutionError
from tests.boilerplate.templates.conftest import git
from tests.integration.boilerplate.composition.staging.conftest import head

SEAM = "boilerplate.composition.staging.copy_back.run_git"


def staging(project: Path, root: Path) -> StagingWorktree:
    return StagingWorktree(project, operation=IntentOperation.UPDATE, temp_root=root)


def commit_layer_changes(stage: StagingWorktree) -> None:
    (stage.path / "added.txt").write_text("added\n", encoding="utf-8")
    (stage.path / "other.txt").write_text("other\n", encoding="utf-8")
    (stage.path / "edit.txt").write_text("edited\n", encoding="utf-8")
    (stage.path / "drop.txt").unlink()
    stage.commit_layer("layer one")


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


class TestPartialCopyBack:
    def test_checkout_is_restored_to_the_starting_commit(
        self, project: Path, staging_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        start = head(project)
        monkeypatch.setattr(SEAM, restore_dying_after_one_file(disk_full()))
        with (
            pytest.raises(UpdateCopyBackFailedError),
            staging(project, staging_root) as stage,
        ):
            commit_layer_changes(stage)
            stage.copy_back()

        assert (head(project), git(project, "status", "--porcelain")) == (start, "")
        assert not (project / "added.txt").exists()
        assert (project / "drop.txt").is_file()

    def test_worktree_is_kept_and_the_error_names_its_path(
        self, project: Path, staging_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(SEAM, restore_dying_after_one_file(disk_full()))
        with (
            pytest.raises(UpdateCopyBackFailedError) as raised,
            staging(project, staging_root) as stage,
        ):
            kept = stage.path
            commit_layer_changes(stage)
            stage.copy_back()

        assert str(kept) in str(raised.value)
        assert raised.value.staging_path == str(kept)
        assert (kept / "other.txt").read_text(encoding="utf-8") == "other\n"
        assert raised.value.error_code == "BP_UPDATE_COPY_BACK_FAILED"

    def test_kept_worktree_survives_a_later_stale_cleanup(
        self, project: Path, staging_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(SEAM, restore_dying_after_one_file(disk_full()))
        with (
            pytest.raises(UpdateCopyBackFailedError),
            staging(project, staging_root) as stage,
        ):
            kept = stage.path
            commit_layer_changes(stage)
            stage.copy_back()

        removed = remove_stale_staging(
            staging_root, now=datetime.now(UTC) + timedelta(days=30)
        )

        assert removed == ()
        assert kept.is_dir()
        assert not (kept.parent / JOURNAL_NAME).exists()

    def test_interrupt_restores_and_keeps_then_propagates(
        self, project: Path, staging_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(SEAM, restore_dying_after_one_file(KeyboardInterrupt()))
        with pytest.raises(KeyboardInterrupt), staging(project, staging_root) as stage:
            kept = stage.path
            commit_layer_changes(stage)
            stage.copy_back()

        assert git(project, "status", "--porcelain") == ""
        assert kept.is_dir()


class TestFailedUndo:
    """The undo of a failed copy back fails too: the checkout keeps part of it."""

    def test_the_error_says_the_checkout_could_not_be_restored(
        self, project: Path, staging_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Never tell the user the checkout was restored when the undo failed."""
        monkeypatch.setattr(
            "boilerplate.composition.staging.copy_back.run_git",
            restore_and_undo_dying(file_in_use()),
        )
        with (
            pytest.raises(UpdateCopyBackFailedError) as raised,
            staging(project, staging_root) as stage,
        ):
            commit_layer_changes(stage)
            stage.copy_back()

        assert "could not be restored" in str(raised.value)

    def test_the_error_names_both_failures(
        self, project: Path, staging_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Report the copy back's failure and the undo's, so both can be fixed."""
        monkeypatch.setattr(
            "boilerplate.composition.staging.copy_back.run_git",
            restore_and_undo_dying(file_in_use()),
        )
        with (
            pytest.raises(UpdateCopyBackFailedError) as raised,
            staging(project, staging_root) as stage,
        ):
            commit_layer_changes(stage)
            stage.copy_back()

        message = str(raised.value)
        assert ("No space left" in message, "Permission denied" in message) == (
            True,
            True,
        )

    def test_an_interrupt_in_the_undo_keeps_the_worktree(
        self, project: Path, staging_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Keep the walk's result, as design 06 requires, when Ctrl-C hits the undo."""
        monkeypatch.setattr(
            "boilerplate.composition.staging.copy_back.run_git",
            restore_and_undo_dying(KeyboardInterrupt()),
        )
        with pytest.raises(KeyboardInterrupt), staging(project, staging_root) as stage:
            kept = stage.path
            commit_layer_changes(stage)
            stage.copy_back()

        assert kept.is_dir()
