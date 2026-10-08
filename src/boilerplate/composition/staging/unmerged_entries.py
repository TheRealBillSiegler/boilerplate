"""Replay a worktree's unmerged index entries into the user's checkout."""

from pathlib import Path

from boilerplate.composition.staging.git_commands import run_git

_NO_OBJECT = "0" * 40


def _unmerged_records(worktree: Path) -> list[str]:
    """Return ``git ls-files --unmerged`` records of `worktree`, one per stage."""
    listing = run_git(worktree, "ls-files", "--unmerged", "-z")
    return [record for record in listing.split("\0") if record]


def _path_of(record: str) -> str:
    """Return the path a ``git ls-files --unmerged`` record names."""
    return record.split("\t", 1)[1]


def list_unmerged_paths(worktree: Path) -> tuple[str, ...]:
    """List the paths a worktree's index holds as unmerged.

    A conflicted file has index stages 1, 2 and 3, as Copier records it; the
    path is reported once. This is how the walk detects a paused layer: by what
    git holds, never by Copier's exit status.

    Args:
        worktree: The staging worktree, whose index is read.

    Returns:
        The unmerged paths in index order; empty when the update merged cleanly.
    """
    return tuple(
        dict.fromkeys(_path_of(record) for record in _unmerged_records(worktree))
    )


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
    records = _unmerged_records(worktree)
    if not records:
        return
    paths = dict.fromkeys(_path_of(record) for record in records)
    drops = [f"0 {_NO_OBJECT}\t{path}\0" for path in paths]
    entries = [f"{record}\0" for record in records]
    run_git(
        project, "update-index", "-z", "--index-info", stdin="".join(drops + entries)
    )
