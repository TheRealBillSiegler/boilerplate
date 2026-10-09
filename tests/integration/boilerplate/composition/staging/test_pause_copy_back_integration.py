"""Copying back a worktree whose last layer paused on a conflict."""

import subprocess
from pathlib import Path

import pytest

from boilerplate.common.exceptions import UpdateCheckoutChangedError
from boilerplate.composition.staging import IntentOperation, StagingWorktree
from tests.boilerplate.templates.conftest import git
from tests.integration.boilerplate.composition.staging.conftest import head

BASE = "one\ntwo\nthree\n"
OURS = "one\nTWO (user)\nthree\n"
THEIRS = "one\nTWO (template)\nthree\n"


def staging(project: Path, root: Path) -> StagingWorktree:
    return StagingWorktree(project, operation=IntentOperation.UPDATE, temp_root=root)


def blob(repo: Path, text: str) -> str:
    """Store `text` as a blob in `repo` and return its hash."""
    result = subprocess.run(
        ["git", "hash-object", "-w", "--stdin"],
        cwd=repo,
        input=text.encode(),
        capture_output=True,
        check=True,
    )
    return result.stdout.decode().strip()


def conflict_edit_txt(worktree: Path) -> None:
    """Leave `edit.txt` in the worktree as an update that hit a conflict does.

    The three versions are real blobs; ``git merge-file`` writes the marked
    working-tree file; the index holds stages 1, 2 and 3 and no stage 0, as
    Copier records a conflicted file.
    """
    base, ours, theirs = (blob(worktree, text) for text in (BASE, OURS, THEIRS))
    parts = {}
    for name, text in (("base", BASE), ("ours", OURS), ("theirs", THEIRS)):
        part = worktree.parent / f"{name}.tmp"
        part.write_text(text, encoding="utf-8", newline="\n")
        parts[name] = part
    merged = subprocess.run(
        [
            "git",
            "merge-file",
            "-p",
            str(parts["ours"]),
            str(parts["base"]),
            str(parts["theirs"]),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert merged.returncode == 1, "the versions must conflict"
    (worktree / "edit.txt").write_text(merged.stdout, encoding="utf-8", newline="\n")
    index = (
        f"0 {'0' * 40}\tedit.txt\n"
        f"100644 {base} 1\tedit.txt\n"
        f"100644 {ours} 2\tedit.txt\n"
        f"100644 {theirs} 3\tedit.txt\n"
    )
    subprocess.run(
        ["git", "update-index", "--index-info"],
        cwd=worktree,
        input=index.encode(),
        check=True,
    )


@pytest.fixture
def paused(project: Path, staging_root: Path) -> Path:
    """Pause a two-layer walk on the second layer's conflict; return the checkout."""
    with staging(project, staging_root) as stage:
        (stage.path / "keep.txt").write_text("finished layer\n", encoding="utf-8")
        stage.commit_layer("layer one")
        conflict_edit_txt(stage.path)
        (stage.path / "paused-added.txt").write_text("added\n", encoding="utf-8")
        (stage.path / "drop.txt").unlink()
        stage.copy_back(paused=True)
    return project


class TestPausedCopyBack:
    def test_conflicted_file_shows_as_unmerged(self, paused: Path) -> None:
        assert "UU edit.txt" in git(paused, "status", "--porcelain").splitlines()

    def test_index_lists_stages_one_two_and_three(self, paused: Path) -> None:
        stages = [
            line.split("\t")[0].split()[2]
            for line in git(paused, "ls-files", "-u").splitlines()
        ]

        assert stages == ["1", "2", "3"]

    def test_working_file_carries_the_conflict_markers(self, paused: Path) -> None:
        text = (paused / "edit.txt").read_text(encoding="utf-8")

        assert "<<<<<<<" in text
        assert ">>>>>>>" in text

    def test_commit_is_refused(self, paused: Path) -> None:
        result = subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@e.x", "commit", "-m", "x"],
            cwd=paused,
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode != 0
        assert "unmerged" in (result.stdout + result.stderr).lower()

    def test_finished_layers_are_applied(self, paused: Path) -> None:
        assert (paused / "keep.txt").read_text(encoding="utf-8") == "finished layer\n"

    def test_paused_layers_additions_and_deletions_are_applied(
        self, paused: Path
    ) -> None:
        assert (paused / "paused-added.txt").read_text(encoding="utf-8") == "added\n"
        assert not (paused / "drop.txt").exists()

    def test_nothing_is_committed(self, paused: Path) -> None:
        assert git(paused, "log", "--format=%s").splitlines() == ["initial"]

    def test_only_unmerged_paths_enter_the_index(self, paused: Path) -> None:
        staged = git(paused, "diff", "--cached", "--name-only").splitlines()

        assert sorted(set(staged)) == ["edit.txt"]


class TestSymlinksInAPausedCopyBack:
    """A link the update leaves is carried as a link, wherever it points."""

    @pytest.mark.parametrize(
        "link_target",
        ["../outside.txt", "keep.txt", "missing.txt"],
        ids=["outside-the-project", "inside-the-project", "dangling"],
    )
    def test_link_is_copied_as_a_link(
        self, project: Path, staging_root: Path, link_target: str
    ) -> None:
        (project.parent / "outside.txt").write_text("outside\n", encoding="utf-8")
        with staging(project, staging_root) as stage:
            try:
                (stage.path / "shared").symlink_to(link_target)
            except OSError:
                pytest.skip("creating a symlink needs a privilege this machine lacks")

            stage.copy_back(paused=True)

        assert (project / "shared").is_symlink()
        assert (project / "shared").readlink() == Path(link_target)


def test_changed_checkout_stops_a_paused_copy_back(
    project: Path, staging_root: Path
) -> None:
    with staging(project, staging_root) as stage:
        conflict_edit_txt(stage.path)
        (project / "mine.txt").write_text("mine\n", encoding="utf-8")
        before = head(project)

        with pytest.raises(UpdateCheckoutChangedError):
            stage.copy_back(paused=True)

    assert git(project, "ls-files", "-u") == ""
    assert head(project) == before
