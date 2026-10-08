"""List the files a layer wrote that git ignores, which a commit and copy back skip."""

from pathlib import Path

from boilerplate.composition.staging.git_commands import run_git


def list_ignored_paths(worktree: Path) -> tuple[str, ...]:
    """List the ignored files and folders in a staging worktree.

    The worktree is a fresh checkout of the tracked files, so an ignored path in
    it is one the update or copy wrote. ``git add --all`` leaves it out of the
    layer commit and the copy back restores from that commit, so it never
    reaches the user's checkout. A folder that is wholly ignored is listed once,
    with a trailing slash.

    Args:
        worktree: The staging worktree.

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
