"""Copying a finished staging worktree back into the user's checkout."""

import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from boilerplate.common.exceptions import UpdateCheckoutChangedError
from boilerplate.composition.staging import (
    JOURNAL_NAME,
    IntentJournal,
    IntentOperation,
    StagingWorktree,
)
from boilerplate.composition.staging.copy_back import (
    list_untracked_paths,
    undo_working_tree,
)
from tests.boilerplate.templates.conftest import commit_all, git, init_repo
from tests.integration.boilerplate.composition.staging.conftest import head


def staging(
    project: Path, root: Path, operation: IntentOperation = IntentOperation.UPDATE
) -> StagingWorktree:
    return StagingWorktree(project, operation=operation, temp_root=root)


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


OPERATIONS = [IntentOperation.UPDATE, IntentOperation.ADD]


def move_head(project: Path) -> None:
    (project / "later.txt").write_text("later\n", encoding="utf-8")
    commit_all(project, "user commits during the run")


def dirty_tree(project: Path) -> None:
    (project / "mine.txt").write_text("mine\n", encoding="utf-8")


def copy_back_error(
    project: Path,
    root: Path,
    operation: IntentOperation,
    disturb: Callable[[Path], None],
) -> UpdateCheckoutChangedError:
    with staging(project, root, operation) as stage:
        disturb(project)
        with pytest.raises(UpdateCheckoutChangedError) as stop:
            stage.copy_back()
    return stop.value


@pytest.mark.parametrize("operation", OPERATIONS)
class TestCheckoutChangedNamesTheOperation:
    def test_moved_commit_message(
        self, project: Path, staging_root: Path, operation: IntentOperation
    ) -> None:
        error = copy_back_error(project, staging_root, operation, move_head)

        assert str(error) == (
            f"The checkout moved to another commit while the {operation.value} ran; "
            "nothing was written."
        )

    def test_moved_commit_remediation(
        self, project: Path, staging_root: Path, operation: IntentOperation
    ) -> None:
        error = copy_back_error(project, staging_root, operation, move_head)

        assert error.remediation == f"Run 'boilerplate {operation.value}' again."

    def test_changed_tree_message(
        self, project: Path, staging_root: Path, operation: IntentOperation
    ) -> None:
        error = copy_back_error(project, staging_root, operation, dirty_tree)

        assert str(error) == (
            f"The checkout changed while the {operation.value} ran; "
            "nothing was written."
        )

    def test_changed_tree_remediation(
        self, project: Path, staging_root: Path, operation: IntentOperation
    ) -> None:
        error = copy_back_error(project, staging_root, operation, dirty_tree)

        assert error.remediation == (
            f"Commit or stash your changes, then run 'boilerplate {operation.value}' "
            "again."
        )


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

            assert list_untracked_paths(project) == ("new/added.txt",)

    def test_restores_the_start_state(self, project: Path, staging_root: Path) -> None:
        """Bring back the edited and deleted files and remove the added one."""
        start = head(project)
        with staging(project, staging_root) as stage:
            self.copy_back_changes(stage)

            undo_working_tree(
                project, stage.start_commit, list_untracked_paths(project)
            )

        assert (git(project, "status", "--porcelain"), head(project)) == ("", start)
        assert (project / "edit.txt").read_text(encoding="utf-8") == "one\ntwo\nthree\n"
        assert (project / "drop.txt").is_file()

    def test_removes_the_folders_it_emptied(
        self, project: Path, staging_root: Path
    ) -> None:
        """Leave no empty directory where the update added files."""
        with staging(project, staging_root) as stage:
            self.copy_back_changes(stage)

            undo_working_tree(
                project, stage.start_commit, list_untracked_paths(project)
            )

        assert not (project / "new").exists()

    def test_leaves_a_file_the_user_made_since(
        self, project: Path, staging_root: Path
    ) -> None:
        """Remove only the files listed: the user's own work is never touched."""
        with staging(project, staging_root) as stage:
            self.copy_back_changes(stage)
            listed = list_untracked_paths(project)
            (project / "mine.txt").write_text("mine\n", encoding="utf-8")

            undo_working_tree(project, stage.start_commit, listed)

        assert (project / "mine.txt").read_text(encoding="utf-8") == "mine\n"

    def test_undoes_what_a_task_wrote_and_staged(
        self, project: Path, staging_root: Path
    ) -> None:
        """Restore the index too, in case a task staged a file."""
        with staging(project, staging_root) as stage:
            self.copy_back_changes(stage)
            (project / "keep.txt").write_text("task edit\n", encoding="utf-8")
            git(project, "add", "keep.txt")

            undo_working_tree(
                project, stage.start_commit, list_untracked_paths(project)
            )

        assert git(project, "status", "--porcelain") == ""


class TestUndoCopyBackWhereUnlinkWouldFail:
    def copy_back_added_dir(self, stage: StagingWorktree) -> None:
        (stage.path / "new").mkdir()
        (stage.path / "new" / "added.txt").write_text("added\n", encoding="utf-8")
        stage.commit_layer("layer one")
        stage.copy_back()

    def test_symlink_is_removed_and_its_target_is_not(
        self, project: Path, staging_root: Path
    ) -> None:
        """Remove the link itself; never follow it to the file it names."""
        with staging(project, staging_root) as stage:
            stage.copy_back()
            try:
                (project / "link.txt").symlink_to("keep.txt")
            except OSError:
                pytest.skip("this platform cannot create symlinks unprivileged")

            undo_working_tree(project, stage.start_commit, ["link.txt"])

        assert not (project / "link.txt").is_symlink()
        assert (project / "keep.txt").read_text(encoding="utf-8") == "keep\n"

    def test_symlink_to_a_file_outside_the_project_is_removed(
        self, project: Path, staging_root: Path, tmp_path: Path
    ) -> None:
        """Treat a link out of the project as the link it is, not as an escape."""
        outside = tmp_path / "outside.txt"
        outside.write_text("outside\n", encoding="utf-8")
        with staging(project, staging_root) as stage:
            stage.copy_back()
            try:
                (project / "link.txt").symlink_to(outside)
            except OSError:
                pytest.skip("this platform cannot create symlinks unprivileged")

            undo_working_tree(project, stage.start_commit, ["link.txt"])

        assert not (project / "link.txt").is_symlink()
        assert outside.read_text(encoding="utf-8") == "outside\n"

    def test_parent_the_user_deleted_does_not_stop_the_undo(
        self, project: Path, staging_root: Path
    ) -> None:
        """Skip a listed path whose folder is already gone and finish restoring."""
        with staging(project, staging_root) as stage:
            self.copy_back_added_dir(stage)
            (project / "keep.txt").write_text("task edit\n", encoding="utf-8")
            listed = list_untracked_paths(project)
            shutil.rmtree(project / "new")

            undo_working_tree(project, stage.start_commit, listed)

        assert (project / "keep.txt").read_text(encoding="utf-8") == "keep\n"
        assert git(project, "status", "--porcelain") == ""

    def test_nested_repository_listed_as_a_directory_does_not_raise(
        self, project: Path, staging_root: Path
    ) -> None:
        """Leave a nested repository alone instead of unlinking a directory."""
        with staging(project, staging_root) as stage:
            stage.copy_back()
            nested = project / "nested"
            nested.mkdir()
            init_repo(nested)
            (nested / "inner.txt").write_text("inner\n", encoding="utf-8")
            listed = list_untracked_paths(project)
            assert listed == ("nested/",)

            undo_working_tree(project, stage.start_commit, listed)

        assert (nested / "inner.txt").read_text(encoding="utf-8") == "inner\n"
