"""A copy back that fails partway restores the checkout and keeps the worktree."""

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
from tests.boilerplate.templates.conftest import git
from tests.integration.boilerplate.composition.staging.conftest import (
    disk_full,
    file_in_use,
    head,
    restore_and_undo_dying,
    restore_dying_after_one_file,
)

SEAM = "boilerplate.composition.staging.copy_back.run_git"


def staging(project: Path, root: Path) -> StagingWorktree:
    return StagingWorktree(project, operation=IntentOperation.UPDATE, temp_root=root)


def commit_layer_changes(stage: StagingWorktree) -> None:
    (stage.path / "added.txt").write_text("added\n", encoding="utf-8")
    (stage.path / "other.txt").write_text("other\n", encoding="utf-8")
    (stage.path / "edit.txt").write_text("edited\n", encoding="utf-8")
    (stage.path / "drop.txt").unlink()
    stage.commit_layer("layer one")


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


# A cause that ends its own sentence, as the staging module's refusals do.
SENTENCE_CAUSE = "'x' escapes the project."


class TestFailureMessage:
    """Each failure is joined into the message with one period after it, not two."""

    def test_a_copy_back_cause_ending_in_a_period_is_joined_once(
        self, project: Path, staging_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Join the cause and the sentence after it with one period, not two."""
        monkeypatch.setattr(
            "boilerplate.composition.staging.copy_back.run_git",
            restore_dying_after_one_file(ValueError(SENTENCE_CAUSE)),
        )
        with (
            pytest.raises(UpdateCopyBackFailedError) as raised,
            staging(project, staging_root) as stage,
        ):
            commit_layer_changes(stage)
            stage.copy_back()

        assert f"{SENTENCE_CAUSE} Your checkout was restored" in str(raised.value)

    def test_an_undo_cause_ending_in_a_period_is_joined_once(
        self, project: Path, staging_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Join the undo's cause and the sentence after it with one period, not two."""
        monkeypatch.setattr(
            "boilerplate.composition.staging.copy_back.run_git",
            restore_and_undo_dying(ValueError(SENTENCE_CAUSE)),
        )
        with (
            pytest.raises(UpdateCopyBackFailedError) as raised,
            staging(project, staging_root) as stage,
        ):
            commit_layer_changes(stage)
            stage.copy_back()

        assert f"{SENTENCE_CAUSE} Your checkout could not be restored" in str(
            raised.value
        )
