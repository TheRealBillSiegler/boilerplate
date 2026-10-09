"""Copying back a worktree whose last layer paused on a conflict."""

import stat
import subprocess
import sys
from pathlib import Path

import pytest

from boilerplate.common.exceptions import UpdateCheckoutChangedError
from boilerplate.composition.staging import IntentOperation, StagingWorktree
from tests.boilerplate.templates.conftest import commit_all, git
from tests.integration.boilerplate.composition.staging.conftest import FILES, head

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


def link_in_worktree(stage: StagingWorktree, link_target: str) -> None:
    """Add a link `shared` to `link_target` in the staging worktree, or skip."""
    try:
        (stage.path / "shared").symlink_to(link_target)
    except OSError:
        pytest.skip("creating a symlink needs a privilege this machine lacks")


class TestSymlinksInAPausedCopyBack:
    """A link the update leaves is carried as a link; one leaving staging is refused.

    The seam is ``StagingWorktree.copy_back(paused=True)``. The refusal is the
    rule in ``docs/design/03-template-system.md``: a symlink in rendered output
    that points outside the staging directory is rejected with a clear error.
    """

    @pytest.mark.parametrize(
        "link_target",
        ["keep.txt", "missing.txt"],
        ids=["inside-the-project", "dangling"],
    )
    def test_link_is_copied_as_a_link(
        self, project: Path, staging_root: Path, link_target: str
    ) -> None:
        with staging(project, staging_root) as stage:
            link_in_worktree(stage, link_target)

            stage.copy_back(paused=True)

        assert (project / "shared").readlink() == Path(link_target)

    def test_directory_link_is_copied_as_a_directory_link(
        self, project: Path, staging_root: Path
    ) -> None:
        """Copy a link to a directory back still a directory link.

        The seam is ``StagingWorktree.copy_back``; the source of truth is the
        link kind the worktree holds. It fails if the copy recreates the link
        as a file link, which Windows does when the target is not yet in the
        checkout. ``aaa`` sorts before ``libdir``, so its target is absent when
        the link is written.
        """
        with staging(project, staging_root) as stage:
            (stage.path / "libdir").mkdir()
            (stage.path / "libdir" / "inner.txt").write_text("x\n", encoding="utf-8")
            try:
                (stage.path / "aaa").symlink_to("libdir", target_is_directory=True)
            except OSError:
                pytest.skip("creating a symlink needs a privilege this machine lacks")

            stage.copy_back(paused=True)

        link = project / "aaa"
        assert link.is_symlink()
        if sys.platform == "win32":
            kind = link.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_DIRECTORY
            assert kind, "the link is a file link, not a directory link"
        else:
            assert link.is_dir()

    @pytest.mark.parametrize(
        "link_target",
        ["../outside.txt", "/outside/elsewhere.txt"],
        ids=["relative", "absolute"],
    )
    def test_link_leaving_the_staging_directory_is_refused(
        self, project: Path, staging_root: Path, link_target: str
    ) -> None:
        with staging(project, staging_root) as stage:
            link_in_worktree(stage, link_target)

            with pytest.raises(ValueError, match="outside the staging directory"):
                stage.copy_back(paused=True)


@pytest.fixture
def linked_project(project: Path) -> Path:
    """Commit a link `shared` to `keep.txt` in the project; return the checkout."""
    try:
        (project / "shared").symlink_to("keep.txt")
    except OSError:
        pytest.skip("creating a symlink needs a privilege this machine lacks")
    commit_all(project, "add a link")
    return project


class TestReplacingACommittedSymlinkInAPausedCopyBack:
    """What the update leaves where the checkout holds a link replaces the link.

    The seam is ``StagingWorktree.copy_back(paused=True)``; the expected state is
    the worktree's own. The tests fail if the copy writes through the checkout's
    link instead of replacing it.
    """

    @pytest.fixture
    def file_replaces_link(self, linked_project: Path, staging_root: Path) -> Path:
        with staging(linked_project, staging_root) as stage:
            (stage.path / "shared").unlink()
            (stage.path / "shared").write_text("replacement\n", encoding="utf-8")
            stage.copy_back(paused=True)
        return linked_project

    @pytest.fixture
    def link_replaces_link(self, linked_project: Path, staging_root: Path) -> Path:
        with staging(linked_project, staging_root) as stage:
            (stage.path / "shared").unlink()
            (stage.path / "shared").symlink_to("edit.txt")
            stage.copy_back(paused=True)
        return linked_project

    def test_file_takes_the_links_place(self, file_replaces_link: Path) -> None:
        shared = file_replaces_link / "shared"

        assert (shared.is_symlink(), shared.read_text(encoding="utf-8")) == (
            False,
            "replacement\n",
        )

    def test_file_is_not_written_through_the_link(
        self, file_replaces_link: Path
    ) -> None:
        keep = (file_replaces_link / "keep.txt").read_text(encoding="utf-8")

        assert keep == FILES["keep.txt"]

    def test_link_takes_the_links_place(self, link_replaces_link: Path) -> None:
        assert (link_replaces_link / "shared").readlink() == Path("edit.txt")


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
