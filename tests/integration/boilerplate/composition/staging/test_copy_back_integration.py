"""Copying a finished staging worktree back into the user's checkout."""

from pathlib import Path

import pytest

from boilerplate.common.exceptions import UpdateCheckoutChangedError
from boilerplate.composition.staging import (
    JOURNAL_NAME,
    IntentJournal,
    IntentOperation,
    StagingWorktree,
)
from tests.boilerplate.templates.conftest import commit_all, git
from tests.integration.boilerplate.composition.staging.conftest import head


def staging(project: Path, root: Path) -> StagingWorktree:
    return StagingWorktree(project, operation=IntentOperation.UPDATE, temp_root=root)


def make_layer_changes(worktree: Path) -> None:
    (worktree / "added.txt").write_text("added\n", encoding="utf-8")
    (worktree / "edit.txt").write_text("edited\n", encoding="utf-8")
    (worktree / "drop.txt").unlink()


class TestCopyBack:
    def test_applies_an_added_a_modified_and_a_deleted_file(
        self, project: Path, staging_root: Path
    ) -> None:
        with staging(project, staging_root) as stage:
            make_layer_changes(stage.path)
            stage.commit_layer("layer one")

            stage.copy_back()

        assert (project / "added.txt").read_text(encoding="utf-8") == "added\n"
        assert (project / "edit.txt").read_text(encoding="utf-8") == "edited\n"
        assert not (project / "drop.txt").exists()
        assert (project / "keep.txt").read_text(encoding="utf-8") == "keep\n"

    def test_changes_stay_uncommitted_and_unstaged(
        self, project: Path, staging_root: Path
    ) -> None:
        start = head(project)
        with staging(project, staging_root) as stage:
            make_layer_changes(stage.path)
            stage.commit_layer("layer one")

            stage.copy_back()

        assert head(project) == start
        assert sorted(git(project, "status", "--porcelain").splitlines()) == [
            " D drop.txt",
            " M edit.txt",
            "?? added.txt",
        ]

    def test_two_layers_apply_together(self, project: Path, staging_root: Path) -> None:
        with staging(project, staging_root) as stage:
            (stage.path / "edit.txt").write_text("first\n", encoding="utf-8")
            stage.commit_layer("layer one")
            (stage.path / "edit.txt").write_text("second\n", encoding="utf-8")
            (stage.path / "drop.txt").unlink()
            stage.commit_layer("layer two")

            stage.copy_back()

        assert (project / "edit.txt").read_text(encoding="utf-8") == "second\n"
        assert not (project / "drop.txt").exists()

    def test_copy_back_with_no_layer_changes_nothing(
        self, project: Path, staging_root: Path
    ) -> None:
        with staging(project, staging_root) as stage:
            stage.copy_back()

        assert git(project, "status", "--porcelain") == ""

    def test_phase_change_keeps_the_start_time(
        self, project: Path, staging_root: Path
    ) -> None:
        with staging(project, staging_root) as stage:
            before = IntentJournal.read(stage.folder).started_at

            stage.copy_back()

            assert IntentJournal.read(stage.folder).started_at == before

    def test_journal_moves_to_the_committing_phase(
        self, project: Path, staging_root: Path
    ) -> None:
        with staging(project, staging_root) as stage:
            stage.copy_back()

            assert IntentJournal.read(stage.folder).phase == "committing"
            assert not (stage.path / JOURNAL_NAME).exists()


class TestCheckoutChanged:
    def test_commit_made_during_staging_stops_the_copy_back(
        self, project: Path, staging_root: Path
    ) -> None:
        with staging(project, staging_root) as stage:
            make_layer_changes(stage.path)
            stage.commit_layer("layer one")
            (project / "later.txt").write_text("later\n", encoding="utf-8")
            commit_all(project, "user commits during the walk")
            user_head = head(project)

            with pytest.raises(UpdateCheckoutChangedError):
                stage.copy_back()

        assert head(project) == user_head
        assert git(project, "status", "--porcelain") == ""
        assert (project / "drop.txt").exists()
        assert not (project / "added.txt").exists()
        assert (project / "edit.txt").read_text(encoding="utf-8") == "one\ntwo\nthree\n"

    def test_uncommitted_edit_made_during_staging_is_kept(
        self, project: Path, staging_root: Path
    ) -> None:
        with staging(project, staging_root) as stage:
            make_layer_changes(stage.path)
            stage.commit_layer("layer one")
            (project / "edit.txt").write_text("my edit\n", encoding="utf-8")

            with pytest.raises(UpdateCheckoutChangedError):
                stage.copy_back()

        assert (project / "edit.txt").read_text(encoding="utf-8") == "my edit\n"
        assert (project / "drop.txt").exists()

    def test_untracked_file_made_during_staging_stops_the_copy_back(
        self, project: Path, staging_root: Path
    ) -> None:
        with staging(project, staging_root) as stage:
            (project / "mine.txt").write_text("mine\n", encoding="utf-8")

            with pytest.raises(UpdateCheckoutChangedError):
                stage.copy_back()

        assert (project / "mine.txt").exists()

    def test_error_leaves_the_worktree_to_be_removed_on_exit(
        self, project: Path, staging_root: Path
    ) -> None:
        with (
            pytest.raises(UpdateCheckoutChangedError),
            staging(project, staging_root) as stage,
        ):
            folder = stage.folder
            (project / "mine.txt").write_text("mine\n", encoding="utf-8")
            stage.copy_back()

        assert not folder.exists()
