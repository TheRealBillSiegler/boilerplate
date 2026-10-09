"""What the update walk reads from, and does to, a staging worktree."""

from pathlib import Path

from boilerplate.composition.staging import (
    IntentJournal,
    IntentOperation,
    StagingWorktree,
)
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
