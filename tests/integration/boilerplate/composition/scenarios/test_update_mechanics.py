"""What Copier's update does with the views, answers and tasks a layer update hands it.

Copier renders an update three times: an old copy at the recorded ref, the
project in place and a new copy at the target ref, then applies the
old-to-new diff. These scenarios pin where tasks run (S16) and how a
conflicting user edit is left for the user (S20), and check the answer
layering through Copier's recording. They run on the made-up template family.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

import pytest

from tests.boilerplate.templates.conftest import (
    commit_all,
    compose_project,
    git,
    update_layer,
)
from tests.integration.boilerplate.composition.family import Family
from tests.integration.boilerplate.composition.scenarios.builders import (
    ANSWERS,
    AUTHOR,
    Recording,
    add_user_line,
    append,
    build_releases,
    build_repos,
    compose_family,
    lines,
    make_git_project,
    merge_state,
    recording_worker,
    substitute,
    temp_dir_inside,
    update_family_layer,
    write,
)

# ------------------------------------------------------------------ S16

MARKER = ".core-task-marker"
TASK_LINE = "core task ran"
TASK_BEFORE = {"core": "1.0.0", "service": "1.0.0", "docs": "1.0.0", "app": "1.0.0"}
TASK_CORE = {**TASK_BEFORE, "core": "1.1.0"}
TASK_SERVICE = {**TASK_CORE, "service": "1.1.0"}


class TaskWalk(NamedTuple):
    """The task marker at compose, and the renders of each layer's update."""

    compose_marker: list[str]
    core: Recording
    marker_before_service: list[str]
    service: Recording


@pytest.fixture(scope="module")
def task_walk(
    family: Family, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[TaskWalk]:
    """Compose the diamond with tasks, then update core and service with tasks."""
    work = tmp_path_factory.mktemp("tasks")
    with temp_dir_inside(work):
        project = compose_family(family, work, "app", TASK_BEFORE, skip_tasks=False)
        compose_marker = lines(project / MARKER)
        core_worker, core = recording_worker([MARKER])
        update_family_layer(
            family,
            project,
            root="app",
            layer="core",
            before=TASK_BEFORE,
            after=TASK_CORE,
            work=work,
            skip_tasks=False,
            worker_type=core_worker,
        )
        commit_all(project, "update core")
        marker_before_service = lines(project / MARKER)
        service_worker, service = recording_worker([MARKER])
        update_family_layer(
            family,
            project,
            root="app",
            layer="service",
            before=TASK_CORE,
            after=TASK_SERVICE,
            work=work,
            skip_tasks=False,
            worker_type=service_worker,
        )
        yield TaskWalk(compose_marker, core, marker_before_service, service)


def _marker_lines(recording: Recording) -> dict[str, list[str]]:
    """Return the marker's lines in each render the recording saw."""
    return {
        role: (copy[MARKER] or "").splitlines()
        for role, copy in recording.copies.items()
    }


@pytest.mark.xdist_group("mechanics-tasks")
class TestTasks:
    """S16: where core's task runs at compose and at update."""

    def test_compose_runs_the_task_once_in_the_destination(
        self, task_walk: TaskWalk
    ) -> None:
        """S16: the merged task runs once across the diamond, in the project folder."""
        assert task_walk.compose_marker == [TASK_LINE]

    def test_update_runs_the_layers_own_task_in_each_of_copiers_renders(
        self, task_walk: TaskWalk
    ) -> None:
        """S16: core's update runs core's task three times.

        Copier runs it in the old copy, in place and in the new copy; in
        place it appends to the line compose left.
        """
        assert _marker_lines(task_walk.core) == {
            "old_copy": [TASK_LINE],
            "in_place": [TASK_LINE, TASK_LINE],
            "new_copy": [TASK_LINE],
        }

    def test_update_of_a_layer_without_a_task_runs_none(
        self, task_walk: TaskWalk
    ) -> None:
        """S16: service declares no task of its own, so its update runs none."""
        assert _marker_lines(task_walk.service) == {
            "old_copy": [],
            "in_place": task_walk.marker_before_service,
            "new_copy": [],
        }


# The in-place claim stays on the bundled layers: the merge undoes the in-place
# line only when the user's side also differs from the old copy's, which two
# layers appending to one marker arranges and the family's single task does not.
MARKER_TASK = """
  - - "{{ _copier_python }}"
    - -c
    - |
      with open("task-marker.txt", "a", encoding="utf-8") as fh:
          fh.write("LAYER\\n")
"""
BUNDLED_TASKS = '_tasks:\n  -  ["{{ _copier_python }}", _scripts/post_generation.py]\n'


def _marker_tasks(ref: str, release: Path) -> None:
    """Give each bundled layer a task that appends its name to a marker file."""
    substitute(
        release / "project" / "copier.yml",
        BUNDLED_TASKS,
        "_tasks:" + MARKER_TASK.replace("LAYER", "project"),
    )
    append(
        release / "streamlit" / "copier.yml",
        "\n_tasks:" + MARKER_TASK.replace("LAYER", "streamlit"),
    )
    write(release / "project" / "project_own.txt.jinja", f"release={ref}\n")


@pytest.fixture(scope="module")
def bundled_marker(tmp_path_factory: pytest.TempPathFactory) -> Iterator[list[str]]:
    """Compose the bundled layers with tasks, then update both with tasks."""
    root = tmp_path_factory.mktemp("bundled-tasks")
    with temp_dir_inside(root):
        releases = build_releases(root, ("v1", "v2"), _marker_tasks)
        repos = build_repos(root, releases)
        project = root / "composed" / "probe-app"
        compose_project("streamlit", project, ANSWERS, releases["v1"], skip_tasks=False)
        make_git_project(project, repos, "v1")
        add_user_line(project / "README.md")
        for layer in ("project", "streamlit"):
            update_layer(
                project,
                root="streamlit",
                layer=layer,
                source=repos[layer],
                ref="v2",
                templates=releases,
                skip_tasks=False,
            )
            commit_all(project, f"update {layer} to v2")
        yield lines(project / "task-marker.txt")


@pytest.mark.xdist_group("mechanics-bundled-tasks")
def test_in_place_task_output_is_undone_by_the_merge(bundled_marker: list[str]) -> None:
    """S16: the marker lines the in-place tasks append do not survive the update."""
    assert bundled_marker == ["project", "streamlit"]


# ------------------------------------------------------------------ S20

CONFLICT_BEFORE = {"core": "2.0.0"}
CONFLICT_AFTER = {"core": "2.1.0"}
README_LINE = "A Python 3.11 project by Ada Probe."


class ConflictUpdate(NamedTuple):
    """Core updated to 2.1.0 over a user edit of the line that release changes."""

    project: Path
    raised: BaseException | None


@pytest.fixture(scope="module")
def conflict(
    family: Family, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[ConflictUpdate]:
    """Edit the README line 2.1.0 rewrites, then update core with data={}.

    Core 2.1.0 drops Python 3.11 and its migration moves a recorded 3.11 to
    3.12, which rewrites the README line naming the version.
    """
    work = tmp_path_factory.mktemp("conflict")
    with temp_dir_inside(work):
        project = compose_family(
            family,
            work,
            "core",
            CONFLICT_BEFORE,
            {"maintainer_name": AUTHOR, "python_version": "3.11"},
        )
        substitute(project / "README.md", README_LINE, f"{README_LINE} (user fork)")
        commit_all(project, "user edits the version line")
        raised: BaseException | None = None
        try:
            update_family_layer(
                family,
                project,
                root="core",
                layer="core",
                before=CONFLICT_BEFORE,
                after=CONFLICT_AFTER,
                work=work,
                data={},
                quiet=False,
            )
        except Exception as exc:  # the outcome under test
            raised = exc
        yield ConflictUpdate(project, raised)


@pytest.mark.xdist_group("mechanics-conflict")
class TestConflictPauses:
    """S20: a user edit of the line a release changes pauses the update."""

    def test_update_returns_without_raising(self, conflict: ConflictUpdate) -> None:
        """S20: Copier finishes the update; the conflict is not an exception."""
        assert conflict.raised is None

    def test_conflict_markers_carry_both_versions(
        self, conflict: ConflictUpdate
    ) -> None:
        """S20: README holds inline markers around the user's and 2.1.0's line."""
        assert lines(conflict.project / "README.md")[2:7] == [
            "<<<<<<< before updating",
            f"{README_LINE} (user fork)",
            "=======",
            "A Python 3.12 project by Ada Probe.",
            ">>>>>>> after updating",
        ]

    def test_conflict_is_visible_to_git_as_unmerged(
        self, conflict: ConflictUpdate
    ) -> None:
        """S20: git reports README unmerged, with base, ours and theirs staged.

        The release's other changes, to the answers file and the pyproject
        version floor, apply cleanly.
        """
        stages = [
            line.split()[2]
            for line in git(
                conflict.project, "ls-files", "--stage", "README.md"
            ).splitlines()
        ]

        assert (git(conflict.project, "status", "--short").splitlines(), stages) == (
            [" M .copier-answers.core.yml", "UU README.md", " M pyproject.toml"],
            ["1", "2", "3"],
        )

    def test_conflict_leaves_no_reject_file(self, conflict: ConflictUpdate) -> None:
        """S20: the inline conflict mode leaves no .rej file behind."""
        assert merge_state(conflict.project).rejects == []
