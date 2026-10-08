"""What the update walk reads from, and does to, a staging worktree."""

from pathlib import Path

from boilerplate.composition.staging import (
    IntentJournal,
    IntentOperation,
    StagingWorktree,
)
from tests.boilerplate.templates.conftest import git
from tests.integration.boilerplate.composition.staging.conftest import head
from tests.integration.boilerplate.composition.staging.test_pause_copy_back_integration import (
    conflict_edit_txt,
)


def staging(project: Path, root: Path) -> StagingWorktree:
    return StagingWorktree(project, operation=IntentOperation.UPDATE, temp_root=root)


class TestUnmergedPaths:
    def test_none_before_a_conflict(self, project: Path, staging_root: Path) -> None:
        """Report nothing for a worktree whose update merged cleanly."""
        with staging(project, staging_root) as stage:
            (stage.path / "edit.txt").write_text("edited\n", encoding="utf-8")

            assert stage.unmerged_paths() == ()

    def test_lists_each_conflicted_path_once(
        self, project: Path, staging_root: Path
    ) -> None:
        """Collapse index stages 1, 2 and 3 of one file to one path."""
        with staging(project, staging_root) as stage:
            conflict_edit_txt(stage.path)

            assert stage.unmerged_paths() == ("edit.txt",)


class TestRecordPhase:
    def test_rewrites_the_journal_beside_the_worktree(
        self, project: Path, staging_root: Path
    ) -> None:
        """Name the locking phase in the journal before the lock is written."""
        with staging(project, staging_root) as stage:
            stage.record_phase("locking")

            assert IntentJournal.read(stage.folder).phase == "locking"


class TestUndoCopyBack:
    def copy_back_changes(self, stage: StagingWorktree) -> None:
        """Commit an edit, an addition in a new folder and a deletion; copy back."""
        (stage.path / "edit.txt").write_text("edited\n", encoding="utf-8")
        (stage.path / "new").mkdir()
        (stage.path / "new" / "added.txt").write_text("added\n", encoding="utf-8")
        (stage.path / "drop.txt").unlink()
        stage.commit_layer("layer one")
        stage.copy_back()

    def test_lists_the_files_the_copy_back_added(
        self, project: Path, staging_root: Path
    ) -> None:
        """Report untracked paths the way git lists them."""
        with staging(project, staging_root) as stage:
            self.copy_back_changes(stage)

            assert stage.untracked_in_checkout() == ("new/added.txt",)

    def test_restores_the_start_state(self, project: Path, staging_root: Path) -> None:
        """Bring back the edited and deleted files and remove the added one."""
        start = head(project)
        with staging(project, staging_root) as stage:
            self.copy_back_changes(stage)

            stage.undo_copy_back(stage.untracked_in_checkout())

        assert (git(project, "status", "--porcelain"), head(project)) == ("", start)
        assert (project / "edit.txt").read_text(encoding="utf-8") == "one\ntwo\nthree\n"
        assert (project / "drop.txt").is_file()

    def test_removes_the_folders_it_emptied(
        self, project: Path, staging_root: Path
    ) -> None:
        """Leave no empty directory where the update added files."""
        with staging(project, staging_root) as stage:
            self.copy_back_changes(stage)

            stage.undo_copy_back(stage.untracked_in_checkout())

        assert not (project / "new").exists()

    def test_leaves_a_file_the_user_made_since(
        self, project: Path, staging_root: Path
    ) -> None:
        """Remove only the files listed: the user's own work is never touched."""
        with staging(project, staging_root) as stage:
            self.copy_back_changes(stage)
            listed = stage.untracked_in_checkout()
            (project / "mine.txt").write_text("mine\n", encoding="utf-8")

            stage.undo_copy_back(listed)

        assert (project / "mine.txt").read_text(encoding="utf-8") == "mine\n"

    def test_undoes_what_a_task_wrote_and_staged(
        self, project: Path, staging_root: Path
    ) -> None:
        """Restore the index too, in case a task staged a file."""
        with staging(project, staging_root) as stage:
            self.copy_back_changes(stage)
            (project / "keep.txt").write_text("task edit\n", encoding="utf-8")
            git(project, "add", "keep.txt")

            stage.undo_copy_back(stage.untracked_in_checkout())

        assert git(project, "status", "--porcelain") == ""
