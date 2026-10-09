"""List the files and folders git ignores: what a layer wrote, and what an undo left."""

from collections.abc import Collection
from pathlib import Path

from boilerplate.composition.staging.git_commands import run_git


def list_ignored_paths(worktree: Path) -> tuple[str, ...]:
    """List the ignored files and folders in a worktree.

    In a staging worktree, a fresh checkout of the tracked files, an ignored
    path is one the update or copy wrote. ``git add --all`` leaves it out of the
    layer commit and the copy back restores from that commit, so it never
    reaches the user's checkout. A folder that is wholly ignored is listed once,
    with a trailing slash.

    Args:
        worktree: The staging worktree, or the user's checkout.

    Returns:
        The ignored paths relative to the worktree, in git's order.
    """
    listing = run_git(
        worktree,
        "ls-files",
        "--others",
        "--ignored",
        "--exclude-standard",
        "--directory",
        "-z",
    )
    return tuple(path for path in listing.split("\0") if path)


def list_new_ignored_paths(worktree: Path, before: Collection[str]) -> tuple[str, ...]:
    """List the ignored entries in a worktree that `before` did not hold.

    An ignored folder is one entry, so a file that appears inside a folder that
    already existed, such as ``.venv/``, is not seen: only an entry whose name
    is new is reported.

    Args:
        worktree: The user's checkout.
        before: The entries ``list_ignored_paths`` listed earlier.

    Returns:
        The ignored paths listed now and not in `before`, in git's order.
    """
    known = frozenset(before)
    return tuple(path for path in list_ignored_paths(worktree) if path not in known)


def uncarried_warning(layer: str, path: str) -> str:
    """Say that a layer wrote an ignored file the copy back will not carry.

    Args:
        layer: The layer whose update or copy wrote the file.
        path: The ignored path, relative to the project.

    Returns:
        The warning.

    """
    return (
        f"Layer '{layer}' wrote '{path}', which .gitignore ignores; "
        "it is not carried into your checkout."
    )
