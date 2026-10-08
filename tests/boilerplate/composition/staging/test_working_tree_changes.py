"""Reading the changed paths out of ``git status --porcelain=v1 -z``."""

import pytest

from boilerplate.composition.staging.working_tree_changes import parse_changed_paths


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
