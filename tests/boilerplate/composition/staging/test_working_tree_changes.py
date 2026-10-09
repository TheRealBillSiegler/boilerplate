"""Reading the changed paths out of ``git status`` and applying them."""

import subprocess
import sys
from pathlib import Path

import pytest

from boilerplate.composition.staging.working_tree_changes import (
    apply_working_tree_changes,
    parse_changed_paths,
)
from tests.boilerplate.templates.conftest import init_repo


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        ("", ()),
        (" M edit.txt\0", ("edit.txt",)),
        (" D drop.txt\0?? added.txt\0", ("drop.txt", "added.txt")),
        ("UU conflicted.txt\0", ("conflicted.txt",)),
        ("A  staged.txt\0MM both.txt\0", ("staged.txt", "both.txt")),
        ("?? dir with space/a b.txt\0", ("dir with space/a b.txt",)),
        ("?? café.txt\0", ("café.txt",)),
    ],
    ids=[
        "empty",
        "modified",
        "deleted-and-untracked",
        "unmerged",
        "staged-and-both",
        "spaces",
        "non-ascii",
    ],
)
def test_parse_changed_paths(output: str, expected: tuple[str, ...]) -> None:
    assert parse_changed_paths(output) == expected


def link_directory(link: Path, target: Path) -> None:
    """Make `link` a directory link to `target`, or skip where none can be made."""
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        if sys.platform != "win32":
            pytest.skip("this machine cannot create a symlink")
        # Without the symlink privilege Windows still makes a junction, and
        # path resolution follows it as it follows a symlink.
        junction = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True,
            check=False,
        )
        if junction.returncode != 0:
            pytest.skip("this machine can create neither a symlink nor a junction")


def test_path_under_a_directory_link_leaving_the_project_is_refused(
    tmp_path: Path,
) -> None:
    """Refuse a changed path whose directory resolves outside the checkout.

    The seam is ``apply_working_tree_changes``; the expected outcome is the
    refusal its docstring promises. It fails if the guard stops resolving the
    path's directory, since the write would then land beyond the link.
    """
    worktree = tmp_path / "worktree"
    (worktree / "sub").mkdir(parents=True)
    init_repo(worktree)
    (worktree / "sub" / "new.txt").write_text("new\n", encoding="utf-8")
    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    link_directory(project / "sub", outside)

    with pytest.raises(ValueError, match="escapes the project"):
        apply_working_tree_changes(worktree, project)
