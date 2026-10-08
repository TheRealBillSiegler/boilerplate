"""Creating and removing the staging worktree of a throwaway project."""

import shutil
from pathlib import Path

import pytest

from boilerplate.common.exceptions import UpdateProjectNotReadyError
from boilerplate.composition.staging import (
    JOURNAL_NAME,
    IntentJournal,
    IntentOperation,
    StagingWorktree,
)
from tests.boilerplate.templates.conftest import git
from tests.integration.boilerplate.composition.staging.conftest import (
    PROJECT_NAME,
    head,
)


def staging(project: Path, root: Path) -> StagingWorktree:
    return StagingWorktree(project, operation=IntentOperation.UPDATE, temp_root=root)


def install_hook(project: Path, name: str, marker: Path) -> None:
    """Install a hook that records its run by writing `marker`."""
    hook = project / ".git" / "hooks" / name
    hook.write_text(f'#!/bin/sh\necho ran > "{marker.as_posix()}"\n', encoding="utf-8")
    hook.chmod(0o755)


class TestRelativeProject:
    def test_dot_resolves_to_the_checkout_and_names_the_worktree_after_it(
        self, project: Path, staging_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(project)

        with staging(Path(), staging_root) as stage:
            assert stage.project == project.resolve()
            assert stage.path.name == PROJECT_NAME
            assert not stage.folder.is_relative_to(stage.path)

    def test_journal_records_an_absolute_destination(
        self, project: Path, staging_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(project.parent)

        with staging(Path(PROJECT_NAME), staging_root) as stage:
            destination = IntentJournal.read(stage.folder).destination
            assert Path(destination).is_absolute()
            assert Path(destination) == project.resolve()


class TestDiscardLeavesOtherRegistrations:
    def test_discard_does_not_prune_the_users_own_stale_registration(
        self, project: Path, staging_root: Path, tmp_path: Path
    ) -> None:
        orphan = tmp_path / "users-own-worktree"
        git(project, "worktree", "add", "--detach", str(orphan), "HEAD")
        shutil.rmtree(orphan)

        with staging(project, staging_root):
            pass

        assert git(project, "worktree", "list", "--porcelain").count("worktree ") == 2


class TestCreate:
    def test_worktree_is_detached_at_the_current_commit(
        self, project: Path, staging_root: Path
    ) -> None:
        start = head(project)

        with staging(project, staging_root) as stage:
            assert head(stage.path) == start
            assert stage.start_commit == start
            assert (
                git(stage.path, "rev-parse", "--abbrev-ref", "HEAD").strip() == "HEAD"
            )

    def test_worktree_folder_is_named_like_the_project(
        self, project: Path, staging_root: Path
    ) -> None:
        with staging(project, staging_root) as stage:
            assert stage.path.name == PROJECT_NAME
            assert stage.path.parent.parent == staging_root

    def test_worktree_holds_the_projects_files(
        self, project: Path, staging_root: Path
    ) -> None:
        with staging(project, staging_root) as stage:
            assert (stage.path / "edit.txt").read_text(encoding="utf-8") == (
                "one\ntwo\nthree\n"
            )

    def test_journal_sits_beside_the_worktree_not_inside(
        self, project: Path, staging_root: Path
    ) -> None:
        with staging(project, staging_root) as stage:
            assert (stage.path.parent / JOURNAL_NAME).is_file()
            assert not (stage.path / JOURNAL_NAME).exists()
            journal = IntentJournal.read(stage.path.parent)
            assert journal.operation is IntentOperation.UPDATE
            assert journal.phase == "staging"
            assert journal.destination == str(project)
            assert journal.staging_dir == str(stage.path.parent)

    def test_post_checkout_hook_does_not_run(
        self, project: Path, staging_root: Path, tmp_path: Path
    ) -> None:
        marker = tmp_path / "post-checkout-ran"
        install_hook(project, "post-checkout", marker)
        control = tmp_path / "control"
        git(project, "worktree", "add", "--detach", str(control), "HEAD")
        assert marker.exists(), "the control worktree must run the hook"
        marker.unlink()

        with staging(project, staging_root):
            pass

        assert not marker.exists()

    def test_dirty_project_is_refused_without_creating_anything(
        self, project: Path, staging_root: Path
    ) -> None:
        (project / "untracked.txt").write_text("x\n", encoding="utf-8")

        with pytest.raises(UpdateProjectNotReadyError), staging(project, staging_root):
            pass

        assert list(staging_root.iterdir()) == []


class TestRemove:
    def test_normal_exit_removes_folder_and_registration(
        self, project: Path, staging_root: Path
    ) -> None:
        with staging(project, staging_root) as stage:
            folder = stage.path.parent

        assert not folder.exists()
        assert git(project, "worktree", "list", "--porcelain").count("worktree ") == 1

    def test_exception_removes_folder_and_registration(
        self, project: Path, staging_root: Path
    ) -> None:
        folder: Path | None = None

        with (
            pytest.raises(RuntimeError, match="boom"),
            staging(project, staging_root) as stage,
        ):
            folder = stage.path.parent
            raise RuntimeError("boom")

        assert folder is not None
        assert not folder.exists()
        assert git(project, "worktree", "list", "--porcelain").count("worktree ") == 1

    def test_project_is_untouched_by_create_and_remove(
        self, project: Path, staging_root: Path
    ) -> None:
        start = head(project)

        with staging(project, staging_root):
            pass

        assert (head(project), git(project, "status", "--porcelain")) == (start, "")
        assert git(project, "branch", "--list").split() == ["*", "main"]

    def test_removal_survives_a_worktree_with_uncommitted_changes(
        self, project: Path, staging_root: Path
    ) -> None:
        with staging(project, staging_root) as stage:
            (stage.path / "scratch.txt").write_text("x\n", encoding="utf-8")
            (stage.path / "edit.txt").write_text("changed\n", encoding="utf-8")
            folder = stage.path.parent

        assert not folder.exists()
