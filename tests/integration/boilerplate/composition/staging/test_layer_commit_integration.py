"""Committing a layer in the staging worktree with git's plumbing."""

from pathlib import Path

from boilerplate.composition.staging import IntentOperation, StagingWorktree
from tests.boilerplate.templates.conftest import git
from tests.integration.boilerplate.composition.staging.conftest import head


def staging(project: Path, root: Path) -> StagingWorktree:
    return StagingWorktree(project, operation=IntentOperation.UPDATE, temp_root=root)


def install_hook(project: Path, name: str, marker: Path) -> None:
    hook = project / ".git" / "hooks" / name
    hook.write_text(f'#!/bin/sh\necho ran > "{marker.as_posix()}"\n', encoding="utf-8")
    hook.chmod(0o755)


def make_layer_changes(worktree: Path) -> None:
    (worktree / "added.txt").write_text("added\n", encoding="utf-8")
    (worktree / "edit.txt").write_text("edited\n", encoding="utf-8")
    (worktree / "drop.txt").unlink()


class TestCommitLayer:
    def test_returns_the_new_head(self, project: Path, staging_root: Path) -> None:
        with staging(project, staging_root) as stage:
            make_layer_changes(stage.path)

            commit = stage.commit_layer("layer one")

            assert commit == head(stage.path)
            assert commit != stage.start_commit

    def test_worktree_is_clean_afterwards(
        self, project: Path, staging_root: Path
    ) -> None:
        with staging(project, staging_root) as stage:
            make_layer_changes(stage.path)

            stage.commit_layer("layer one")

            assert git(stage.path, "status", "--porcelain") == ""

    def test_commit_holds_additions_edits_and_deletions(
        self, project: Path, staging_root: Path
    ) -> None:
        with staging(project, staging_root) as stage:
            make_layer_changes(stage.path)

            commit = stage.commit_layer("layer one")

            changes = git(
                stage.path, "diff", "--name-status", stage.start_commit, commit
            )
            assert sorted(changes.splitlines()) == [
                "A\tadded.txt",
                "D\tdrop.txt",
                "M\tedit.txt",
            ]

    def test_layers_chain_and_the_message_is_kept(
        self, project: Path, staging_root: Path
    ) -> None:
        with staging(project, staging_root) as stage:
            (stage.path / "one.txt").write_text("1\n", encoding="utf-8")
            first = stage.commit_layer("layer one")
            (stage.path / "two.txt").write_text("2\n", encoding="utf-8")

            second = stage.commit_layer("layer two")

            assert git(stage.path, "rev-parse", f"{second}^").strip() == first
            assert (
                git(stage.path, "log", "-1", "--format=%s", second).strip()
                == "layer two"
            )
            assert stage.last_commit == second

    def test_last_commit_starts_at_the_start_commit(
        self, project: Path, staging_root: Path
    ) -> None:
        with staging(project, staging_root) as stage:
            assert stage.last_commit == stage.start_commit

    def test_no_commit_hook_runs(
        self, project: Path, staging_root: Path, tmp_path: Path
    ) -> None:
        markers = {
            name: tmp_path / f"{name}-ran"
            for name in (
                "pre-commit",
                "commit-msg",
                "post-commit",
                "reference-transaction",
            )
        }
        for name, marker in markers.items():
            install_hook(project, name, marker)
        with staging(project, staging_root) as stage:
            make_layer_changes(stage.path)

            stage.commit_layer("layer one")

        assert [n for n, m in markers.items() if m.exists()] == []

    def test_user_checkout_is_untouched(
        self, project: Path, staging_root: Path
    ) -> None:
        start = head(project)
        with staging(project, staging_root) as stage:
            make_layer_changes(stage.path)
            stage.commit_layer("layer one")

        assert (head(project), git(project, "status", "--porcelain")) == (start, "")
