"""Commit a worktree's whole state with git's plumbing."""

from pathlib import Path

from boilerplate.composition.staging.git_commands import run_git


def commit_worktree(worktree: Path, message: str) -> str:
    """Stage everything in `worktree` and commit it on top of HEAD.

    The commit is built with ``write-tree`` and ``commit-tree`` and HEAD is
    moved with ``update-ref``, so none of the repository's commit hooks run. A
    commit is what lets Copier update the next layer: it refuses to update a
    project whose working tree has changes.

    Args:
        worktree: The worktree to commit; its HEAD becomes the parent.
        message: The commit message.

    Returns:
        The new commit's hash.
    """
    run_git(worktree, "add", "--all")
    tree = run_git(worktree, "write-tree").strip()
    parent = run_git(worktree, "rev-parse", "HEAD").strip()
    commit = run_git(worktree, "commit-tree", tree, "-p", parent, "-m", message).strip()
    run_git(worktree, "update-ref", "HEAD", commit)
    return commit
