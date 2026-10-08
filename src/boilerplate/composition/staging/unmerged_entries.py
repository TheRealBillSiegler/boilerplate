"""Replay a worktree's unmerged index entries into the user's checkout."""

from pathlib import Path

from boilerplate.composition.staging.git_commands import run_git

_NO_OBJECT = "0" * 40


def replay_unmerged_entries(worktree: Path, project: Path) -> None:
    """Write the worktree's conflicted index entries into the checkout's index.

    Copier records each conflicted file as index stages 1, 2 and 3. The
    entries are read with ``git ls-files --unmerged`` in the worktree and
    written with ``git update-index --index-info`` in the checkout, after a
    line that drops the path's stage 0 as Copier does. The worktree shares the
    checkout's object store, so the staged blobs resolve in both. The files
    then show as unmerged and ``git commit`` refuses them.

    Args:
        worktree: The staging worktree, whose index is read.
        project: The user's checkout, whose index is written.
    """
    listing = run_git(worktree, "ls-files", "--unmerged", "-z")
    records = [record for record in listing.split("\0") if record]
    if not records:
        return
    paths = dict.fromkeys(record.split("\t", 1)[1] for record in records)
    drops = [f"0 {_NO_OBJECT}\t{path}\0" for path in paths]
    entries = [f"{record}\0" for record in records]
    run_git(
        project, "update-index", "-z", "--index-info", stdin="".join(drops + entries)
    )
