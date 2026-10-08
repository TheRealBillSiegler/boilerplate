"""Removing the staging folders an interrupted run left behind."""

import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

from boilerplate.composition.staging import (
    JOURNAL_NAME,
    IntentJournal,
    IntentOperation,
    StagingWorktree,
    remove_stale_staging,
)
from tests.boilerplate.templates.conftest import git


def staging(project: Path, root: Path) -> StagingWorktree:
    return StagingWorktree(project, operation=IntentOperation.UPDATE, temp_root=root)


def leave_behind(project: Path, root: Path) -> StagingWorktree:
    """Enter a staging and walk away, as a run whose process died does.

    The operating system drops a dead process's lock, so the helper drops the
    staging's own to match; ``stay_alive`` is the case where it is still held.
    """
    stage = stay_alive(project, root)
    stage._lock.release()  # pyright: ignore[reportPrivateUsage]
    return stage


def stay_alive(project: Path, root: Path) -> StagingWorktree:
    """Enter a staging and keep it open, as a run waiting at a prompt does."""
    return staging(project, root).__enter__()


def registered_worktrees(project: Path) -> int:
    return git(project, "worktree", "list", "--porcelain").count("worktree ")


def started_at(stage: StagingWorktree) -> datetime:
    return IntentJournal.read(stage.folder).started_at


class TestLiveStaging:
    def test_staging_that_holds_its_lock_survives_a_cleanup_far_in_the_future(
        self, project: Path, staging_root: Path
    ) -> None:
        live = stay_alive(project, staging_root)

        removed = remove_stale_staging(
            staging_root, now=started_at(live) + timedelta(days=30)
        )

        assert removed == ()
        assert live.path.is_dir()
        assert registered_worktrees(project) == 2
        live.__exit__(None, None, None)

    def test_staging_that_released_its_lock_is_stale_once_old_enough(
        self, project: Path, staging_root: Path
    ) -> None:
        dead = leave_behind(project, staging_root)
        folder = dead.folder

        removed = remove_stale_staging(
            staging_root, now=started_at(dead) + timedelta(days=30)
        )

        assert removed == (folder,)

    def test_exit_removes_the_lock_file_with_the_folder(
        self, project: Path, staging_root: Path
    ) -> None:
        with staging(project, staging_root) as stage:
            folder = stage.folder

        assert not folder.exists()


class TestRemoveStaleStaging:
    def test_old_marked_folder_and_its_registration_are_removed(
        self, project: Path, staging_root: Path
    ) -> None:
        stale = leave_behind(project, staging_root)
        folder = stale.folder
        later = started_at(stale) + timedelta(hours=2)

        removed = remove_stale_staging(staging_root, now=later)

        assert removed == (folder,)
        assert not folder.exists()
        assert registered_worktrees(project) == 1

    def test_cleanup_prunes_the_registration_of_a_worktree_whose_folder_is_gone(
        self, project: Path, staging_root: Path, tmp_path: Path
    ) -> None:
        orphan = tmp_path / "users-own-worktree"
        git(project, "worktree", "add", "--detach", str(orphan), "HEAD")
        shutil.rmtree(orphan)
        stale = leave_behind(project, staging_root)
        later = started_at(stale) + timedelta(hours=2)

        remove_stale_staging(staging_root, now=later)

        assert registered_worktrees(project) == 1

    def test_fresh_folder_is_left_alone(
        self, project: Path, staging_root: Path
    ) -> None:
        fresh = leave_behind(project, staging_root)
        soon = started_at(fresh) + timedelta(minutes=5)

        removed = remove_stale_staging(staging_root, now=soon)

        assert removed == ()
        assert fresh.path.is_dir()
        assert registered_worktrees(project) == 2
        fresh.__exit__(None, None, None)

    def test_folder_exactly_at_the_window_is_kept(
        self, project: Path, staging_root: Path
    ) -> None:
        edge = leave_behind(project, staging_root)

        removed = remove_stale_staging(
            staging_root, now=started_at(edge) + timedelta(hours=1)
        )

        assert removed == ()
        edge.__exit__(None, None, None)

    def test_old_and_fresh_are_told_apart_in_one_pass(
        self, project: Path, staging_root: Path
    ) -> None:
        old = leave_behind(project, staging_root)
        old_folder = old.folder
        fresh = leave_behind(project, staging_root)
        IntentJournal.read(old_folder).model_copy(
            update={"started_at": datetime.now(UTC) - timedelta(hours=3)}
        ).write(old_folder)

        removed = remove_stale_staging(staging_root)

        assert removed == (old_folder,)
        assert fresh.path.is_dir()
        assert registered_worktrees(project) == 2
        fresh.__exit__(None, None, None)

    def test_folder_without_a_journal_is_not_ours(self, staging_root: Path) -> None:
        foreign = staging_root / "boilerplate-staging-foreign"
        foreign.mkdir()
        (foreign / "data.txt").write_text("keep\n", encoding="utf-8")

        removed = remove_stale_staging(
            staging_root, now=datetime.now(UTC) + timedelta(days=30)
        )

        assert removed == ()
        assert (foreign / "data.txt").exists()

    def test_folder_with_a_journal_but_another_name_is_not_ours(
        self, project: Path, staging_root: Path
    ) -> None:
        other = leave_behind(project, staging_root)
        renamed = staging_root / "someone-elses"
        other.folder.rename(renamed)

        removed = remove_stale_staging(
            staging_root, now=datetime.now(UTC) + timedelta(days=30)
        )

        assert removed == ()
        assert (renamed / JOURNAL_NAME).exists()

    def test_unparseable_journal_is_left_for_inspection(
        self, staging_root: Path
    ) -> None:
        broken = staging_root / "boilerplate-staging-broken"
        broken.mkdir()
        (broken / JOURNAL_NAME).write_text("{not json", encoding="utf-8")

        removed = remove_stale_staging(
            staging_root, now=datetime.now(UTC) + timedelta(days=30)
        )

        assert removed == ()
        assert (broken / JOURNAL_NAME).exists()

    def test_journal_that_is_not_utf8_is_left_for_inspection(
        self, staging_root: Path
    ) -> None:
        broken = staging_root / "boilerplate-staging-binary"
        broken.mkdir()
        (broken / JOURNAL_NAME).write_bytes(bytes([0xFF, 0xFE]))

        removed = remove_stale_staging(
            staging_root, now=datetime.now(UTC) + timedelta(days=30)
        )

        assert removed == ()
        assert (broken / JOURNAL_NAME).exists()

    def test_folder_of_a_deleted_project_is_still_removed(
        self, project: Path, staging_root: Path
    ) -> None:
        orphan = leave_behind(project, staging_root)
        folder = orphan.folder
        later = started_at(orphan) + timedelta(hours=2)
        IntentJournal.read(folder).model_copy(
            update={"destination": str(project.parent / "gone")}
        ).write(folder)

        removed = remove_stale_staging(staging_root, now=later)

        assert removed == (folder,)
        assert not folder.exists()

    def test_missing_root_is_a_no_op(self, tmp_path: Path) -> None:
        assert remove_stale_staging(tmp_path / "absent") == ()


class TestCleanupBeforeCreate:
    def test_entering_a_staging_removes_a_stale_one(
        self, project: Path, staging_root: Path
    ) -> None:
        stale = leave_behind(project, staging_root)
        stale_folder = stale.folder
        IntentJournal.read(stale_folder).model_copy(
            update={"started_at": datetime.now(UTC) - timedelta(hours=2)}
        ).write(stale_folder)

        with staging(project, staging_root) as current:
            assert not stale_folder.exists()
            assert current.path.is_dir()
            assert registered_worktrees(project) == 2
