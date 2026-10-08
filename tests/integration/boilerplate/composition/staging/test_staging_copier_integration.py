"""A real Copier update run inside the staging worktree of a family project."""

import subprocess
from pathlib import Path

import pytest

from boilerplate.composition.staging import IntentOperation, StagingWorktree
from boilerplate.composition.updating import ScopedWorker
from tests.boilerplate.templates.conftest import commit_all, git
from tests.integration.boilerplate.composition.family import Family
from tests.integration.boilerplate.composition.scenarios.builders import (
    AUTHOR,
    answers_file,
    compose_family,
    substitute,
    update_family_layer,
)
from tests.integration.boilerplate.composition.temp_dir import temp_dir_inside

pytestmark = [pytest.mark.scenario]

PROJECT_FOLDER = "family-app"
BEFORE = {"core": "1.0.0", "service": "1.0.0"}
AFTER_CORE = {"core": "1.1.0", "service": "1.0.0"}
AFTER_SERVICE = {"core": "1.1.0", "service": "1.1.0"}


def staging(project: Path, root: Path) -> StagingWorktree:
    return StagingWorktree(project, operation=IntentOperation.UPDATE, temp_root=root)


def folder_name_worker() -> tuple[type[ScopedWorker], list[tuple[str, str]]]:
    """Return a worker class that records the folder name each in-place render sees."""
    seen: list[tuple[str, str]] = []

    class FolderNameWorker(ScopedWorker):
        def run_copy(self) -> None:
            seen.append(
                (Path(str(self.dst_path)).name, self.subproject.local_abspath.name)
            )
            super().run_copy()

    return FolderNameWorker, seen


class TestWalkInTheWorktree:
    def test_second_layer_updates_after_a_plumbing_commit(
        self, family: Family, tmp_path: Path
    ) -> None:
        """Copier's dirty check passes once the first layer is committed."""
        with temp_dir_inside(tmp_path):
            project = compose_family(family, tmp_path, "service", BEFORE)
            with staging(project, _root(tmp_path)) as stage:
                update_family_layer(
                    family,
                    stage.path,
                    root="service",
                    layer="core",
                    before=BEFORE,
                    after=AFTER_CORE,
                    work=tmp_path,
                )
                stage.commit_layer("core 1.1.0")
                assert git(stage.path, "status", "--porcelain") == ""

                update_family_layer(
                    family,
                    stage.path,
                    root="service",
                    layer="service",
                    before=AFTER_CORE,
                    after=AFTER_SERVICE,
                    work=tmp_path,
                )
                stage.commit_layer("service 1.1.0")

                stage.copy_back()

            assert answers_file(project, "core")["_commit"] == "1.1.0"
            assert answers_file(project, "service")["_commit"] == "1.1.0"
            assert (
                git(project, "log", "--format=%s").splitlines()[0].startswith("compose")
            )
            assert git(project, "status", "--porcelain") != ""

    def test_uncommitted_layer_blocks_the_next_one(
        self, family: Family, tmp_path: Path
    ) -> None:
        """Control: without the commit, Copier refuses the second layer."""
        with temp_dir_inside(tmp_path):
            project = compose_family(family, tmp_path, "service", BEFORE)
            with staging(project, _root(tmp_path)) as stage:
                update_family_layer(
                    family,
                    stage.path,
                    root="service",
                    layer="core",
                    before=BEFORE,
                    after=AFTER_CORE,
                    work=tmp_path,
                )

                with pytest.raises(Exception, match="dirty"):
                    update_family_layer(
                        family,
                        stage.path,
                        root="service",
                        layer="service",
                        before=AFTER_CORE,
                        after=AFTER_SERVICE,
                        work=tmp_path,
                    )

    def test_folder_name_resolves_to_the_projects_name(
        self, family: Family, tmp_path: Path
    ) -> None:
        worker, seen = folder_name_worker()
        with temp_dir_inside(tmp_path):
            project = compose_family(family, tmp_path, "service", BEFORE)
            with staging(project, _root(tmp_path)) as stage:
                update_family_layer(
                    family,
                    stage.path,
                    root="service",
                    layer="core",
                    before=BEFORE,
                    after=AFTER_CORE,
                    work=tmp_path,
                    worker_type=worker,
                )

        in_place = [folder for dst, folder in seen if dst == PROJECT_FOLDER]
        assert in_place
        assert set(in_place) == {PROJECT_FOLDER}


class TestConflictInTheWorktree:
    def test_pause_leaves_the_user_checkout_unmerged(
        self, family: Family, tmp_path: Path
    ) -> None:
        before, after = {"core": "2.0.0"}, {"core": "2.1.0"}
        line = "A Python 3.11 project by Ada Probe."
        with temp_dir_inside(tmp_path):
            project = compose_family(
                family,
                tmp_path,
                "core",
                before,
                {"maintainer_name": AUTHOR, "python_version": "3.11"},
            )
            substitute(project / "README.md", line, f"{line} (user fork)")
            commit_all(project, "user edits the version line")
            with staging(project, _root(tmp_path)) as stage:
                update_family_layer(
                    family,
                    stage.path,
                    root="core",
                    layer="core",
                    before=before,
                    after=after,
                    work=tmp_path,
                    data={},
                    quiet=False,
                )
                assert "UU README.md" in git(stage.path, "status", "--porcelain")

                stage.copy_back(paused=True)

            status = git(project, "status", "--porcelain").splitlines()
            stages = [
                row.split("\t")[0].split()[2]
                for row in git(project, "ls-files", "-u").splitlines()
                if row.endswith("README.md")
            ]
            refused = subprocess.run(
                [
                    "git",
                    "-c",
                    "user.name=t",
                    "-c",
                    "user.email=t@e.x",
                    "commit",
                    "-m",
                    "x",
                ],
                cwd=project,
                capture_output=True,
                text=True,
                check=False,
            )

        assert "UU README.md" in status
        assert stages == ["1", "2", "3"]
        assert "<<<<<<<" in (project / "README.md").read_text(encoding="utf-8")
        assert refused.returncode != 0


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "staging-root"
    root.mkdir(exist_ok=True)
    return root
