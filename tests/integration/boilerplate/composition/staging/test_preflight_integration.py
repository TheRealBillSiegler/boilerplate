"""The pre-flight check refuses a project that cannot be staged safely."""

from pathlib import Path

import pytest

from boilerplate.common.exceptions import (
    UpdateProjectNotReadyError,
    UpdateSubmodulesUnsupportedError,
)
from boilerplate.composition.staging import IntentOperation, check_project_ready
from tests.boilerplate.templates.conftest import commit_all, git


class TestAcceptedProject:
    def test_clean_repository_passes(self, project: Path) -> None:
        check_project_ready(project)


class TestRefusedProject:
    def test_modified_file_is_refused(self, project: Path) -> None:
        (project / "edit.txt").write_text("changed\n", encoding="utf-8")

        with pytest.raises(UpdateProjectNotReadyError, match="uncommitted changes"):
            check_project_ready(project)

    def test_untracked_file_is_refused(self, project: Path) -> None:
        (project / "new.txt").write_text("new\n", encoding="utf-8")

        with pytest.raises(UpdateProjectNotReadyError, match="uncommitted changes"):
            check_project_ready(project)

    def test_message_names_the_remedy(self, project: Path) -> None:
        (project / "new.txt").write_text("new\n", encoding="utf-8")

        with pytest.raises(UpdateProjectNotReadyError) as stop:
            check_project_ready(project)

        assert str(stop.value) == (
            "Working tree has uncommitted changes. "
            "Commit or stash them before running boilerplate update."
        )

    def test_message_names_the_command_that_stopped(self, project: Path) -> None:
        (project / "new.txt").write_text("new\n", encoding="utf-8")

        with pytest.raises(UpdateProjectNotReadyError) as stop:
            check_project_ready(project, IntentOperation.ADD)

        assert str(stop.value) == (
            "Working tree has uncommitted changes. "
            "Commit or stash them before running boilerplate add."
        )

    def test_plain_folder_is_refused(self, tmp_path: Path) -> None:
        folder = tmp_path / "plain"
        folder.mkdir()

        with pytest.raises(UpdateProjectNotReadyError, match="git repository"):
            check_project_ready(folder)

    def test_subfolder_of_a_repository_is_refused(self, project: Path) -> None:
        inner = project / "inner"
        inner.mkdir()
        (inner / "f.txt").write_text("x\n", encoding="utf-8")
        commit_all(project, "inner")

        with pytest.raises(UpdateProjectNotReadyError, match="root"):
            check_project_ready(inner)

    def test_submodule_file_names_the_paths(self, project: Path) -> None:
        (project / ".gitmodules").write_text(
            '[submodule "lib"]\n\tpath = vendor/lib\n\turl = https://example.invalid/lib\n',
            encoding="utf-8",
        )
        commit_all(project, "declare a submodule")
        assert git(project, "status", "--porcelain") == ""

        with pytest.raises(UpdateSubmodulesUnsupportedError) as stop:
            check_project_ready(project)

        assert stop.value.paths == ("vendor/lib",)
        assert "vendor/lib" in str(stop.value)
