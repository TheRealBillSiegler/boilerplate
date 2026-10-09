"""The files a layer wrote that git ignores, which the commit and copy back skip."""

from pathlib import Path

from boilerplate.composition.staging.ignored_files import (
    list_ignored_paths,
    list_new_ignored_paths,
    uncarried_warning,
)
from tests.boilerplate.templates.conftest import commit_all, ignore_locally


class TestListIgnoredPaths:
    def test_lists_an_ignored_file_and_a_wholly_ignored_folder_once(
        self, project: Path
    ) -> None:
        """Name the folder once with a slash, as ``git ls-files --directory`` does."""
        (project / ".gitignore").write_text("dist/\n*.log\n", encoding="utf-8")
        commit_all(project, "ignore build output")
        (project / "dist").mkdir()
        (project / "dist" / "a.txt").write_text("a\n", encoding="utf-8")
        (project / "dist" / "b.txt").write_text("b\n", encoding="utf-8")
        (project / "run.log").write_text("log\n", encoding="utf-8")

        assert sorted(list_ignored_paths(project)) == ["dist/", "run.log"]

    def test_lists_nothing_when_the_worktree_holds_only_tracked_files(
        self, project: Path
    ) -> None:
        """Warn about nothing for a worktree whose files are all carried."""
        assert list_ignored_paths(project) == ()


class TestListNewIgnoredPaths:
    def test_lists_only_the_entries_the_earlier_listing_lacked(
        self, project: Path
    ) -> None:
        """Compare by entry name, so an ignored folder counts once."""
        ignore_locally(project, "*.log")
        ignore_locally(project, "dist/")
        (project / "old.log").write_text("old\n", encoding="utf-8")
        before = list_ignored_paths(project)
        (project / "new.log").write_text("new\n", encoding="utf-8")
        (project / "dist").mkdir()
        (project / "dist" / "a.txt").write_text("a\n", encoding="utf-8")

        assert list_new_ignored_paths(project, before) == ("dist/", "new.log")


class TestUncarriedWarning:
    def test_names_the_layer_and_the_path(self) -> None:
        """Say which layer wrote the file and that the copy back leaves it behind."""
        assert uncarried_warning("gen", "dist/") == (
            "Layer 'gen' wrote 'dist/', which .gitignore ignores; "
            "it is not carried into your checkout."
        )
