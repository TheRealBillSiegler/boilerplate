"""Stopping a copy back that would clobber an ignored file or directory."""

from pathlib import Path

import pytest

from boilerplate.common.exceptions import UpdatePathObstructedError
from boilerplate.composition.staging import IntentOperation, StagingWorktree
from tests.boilerplate.templates.conftest import commit_all, git
from tests.integration.boilerplate.composition.staging.conftest import head


def staging(project: Path, root: Path) -> StagingWorktree:
    return StagingWorktree(project, operation=IntentOperation.UPDATE, temp_root=root)


@pytest.fixture
def ignoring_project(project: Path) -> Path:
    """Return `project` with a committed ``.gitignore`` for the ignored names."""
    (project / ".gitignore").write_text(
        "ig.txt\nm/\nother.txt\nf\n", encoding="utf-8", newline="\n"
    )
    commit_all(project, "ignore")
    return project


def add_in_worktree(stage: StagingWorktree, *names: str) -> None:
    """Add each named file to the worktree as the layer's commit; force past ignore."""
    for name in names:
        target = stage.path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("template\n", encoding="utf-8", newline="\n")
    git(stage.path, "add", "--force", "--all")
    stage.commit_layer("layer one")


class TestIgnoredFile:
    def test_copy_back_stops_and_leaves_the_users_file_alone(
        self, ignoring_project: Path, staging_root: Path
    ) -> None:
        (ignoring_project / "ig.txt").write_text("mine\n", encoding="utf-8")
        start = head(ignoring_project)
        with staging(ignoring_project, staging_root) as stage:
            add_in_worktree(stage, "ig.txt", "fresh.txt")

            with pytest.raises(UpdatePathObstructedError) as raised:
                stage.copy_back()

        assert raised.value.paths == ("ig.txt",)
        assert "ig.txt" in str(raised.value)
        assert (ignoring_project / "ig.txt").read_text(encoding="utf-8") == "mine\n"
        assert not (ignoring_project / "fresh.txt").exists()
        assert head(ignoring_project) == start

    def test_error_names_every_obstructed_path(
        self, ignoring_project: Path, staging_root: Path
    ) -> None:
        for name in ("ig.txt", "other.txt"):
            (ignoring_project / name).write_text("mine\n", encoding="utf-8")
        with staging(ignoring_project, staging_root) as stage:
            add_in_worktree(stage, "ig.txt", "other.txt")

            with pytest.raises(UpdatePathObstructedError) as raised:
                stage.copy_back()

        assert sorted(raised.value.paths) == ["ig.txt", "other.txt"]


class TestIgnoredDirectory:
    def test_directory_where_the_walk_adds_a_file_survives(
        self, ignoring_project: Path, staging_root: Path
    ) -> None:
        (ignoring_project / "m").mkdir()
        (ignoring_project / "m" / "keep.txt").write_text("mine\n", encoding="utf-8")
        with staging(ignoring_project, staging_root) as stage:
            add_in_worktree(stage, "m")

            with pytest.raises(UpdatePathObstructedError) as raised:
                stage.copy_back()

        assert raised.value.paths == ("m",)
        assert (ignoring_project / "m" / "keep.txt").read_text(
            encoding="utf-8"
        ) == "mine\n"

    def test_file_where_the_walk_adds_a_directory_is_obstructed(
        self, ignoring_project: Path, staging_root: Path
    ) -> None:
        (ignoring_project / "f").write_text("mine\n", encoding="utf-8")
        with staging(ignoring_project, staging_root) as stage:
            add_in_worktree(stage, "f/inner.txt")

            with pytest.raises(UpdatePathObstructedError) as raised:
                stage.copy_back()

        assert raised.value.paths == ("f/inner.txt",)
        assert (ignoring_project / "f").read_text(encoding="utf-8") == "mine\n"


class TestNoObstruction:
    def test_ignored_directory_beside_a_new_file_is_no_obstruction(
        self, ignoring_project: Path, staging_root: Path
    ) -> None:
        (ignoring_project / "m").mkdir()
        (ignoring_project / "m" / "keep.txt").write_text("mine\n", encoding="utf-8")
        with staging(ignoring_project, staging_root) as stage:
            add_in_worktree(stage, "m/new.txt")

            stage.copy_back()

        assert (ignoring_project / "m" / "keep.txt").exists()
        assert (ignoring_project / "m" / "new.txt").exists()

    def test_a_tracked_file_the_walk_replaces_is_no_obstruction(
        self, project: Path, staging_root: Path
    ) -> None:
        with staging(project, staging_root) as stage:
            (stage.path / "edit.txt").write_text("edited\n", encoding="utf-8")
            (stage.path / "drop.txt").unlink()
            stage.commit_layer("layer one")

            stage.copy_back()

        assert not (project / "drop.txt").exists()


class TestPausedLayer:
    def test_a_file_the_paused_layer_added_is_checked_too(
        self, ignoring_project: Path, staging_root: Path
    ) -> None:
        (ignoring_project / "ig.txt").write_text("mine\n", encoding="utf-8")
        with staging(ignoring_project, staging_root) as stage:
            (stage.path / "ig.txt").write_text("template\n", encoding="utf-8")
            git(stage.path, "add", "--force", "ig.txt")

            with pytest.raises(UpdatePathObstructedError) as raised:
                stage.copy_back(paused=True)

        assert raised.value.paths == ("ig.txt",)
        assert (ignoring_project / "ig.txt").read_text(encoding="utf-8") == "mine\n"
