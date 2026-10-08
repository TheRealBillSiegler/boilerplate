"""What Copier's update does with the views, answers and tasks a layer update hands it.

Copier renders an update three times: an old copy at the recorded ref, the
project in place and a new copy at the target ref, then applies the
old-to-new diff. These scenarios pin which inputs reach which render (S12's
control, and a direct check of the harness's answer layering), where tasks
run (S16) and how a conflicting user edit is left for the user (S20).
"""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any, NamedTuple

import pytest

from tests.integration.boilerplate.composition.scenarios.builders import (
    ANSWERS,
    LICENSE_FILE,
    LicenseProject,
    Recording,
    add_user_line,
    append,
    build_releases,
    build_repos,
    compose_license_project,
    lines,
    make_git_project,
    merge_state,
    recording_worker,
    substitute,
    temp_dir_inside,
    write,
)
from tests.boilerplate.templates.conftest import (
    commit_all,
    compose_project,
    git,
    recorded_answers,
    update_layer,
)

# ------------------------------------------------------------------ S12 control


class RemovalUpdate(NamedTuple):
    """Project updated v4 to v5 (license question removed) with data={}."""

    setup: LicenseProject
    recording: Recording


@pytest.fixture(scope="module")
def removal(tmp_path_factory: pytest.TempPathFactory) -> Iterator[RemovalUpdate]:
    """Compose the license releases at v4, then update project to v5 with data={}."""
    root = tmp_path_factory.mktemp("removal")
    with temp_dir_inside(root):
        setup = compose_license_project(root)
        worker, recording = recording_worker([LICENSE_FILE])
        update_layer(
            setup.project,
            root="streamlit",
            layer="project",
            source=setup.repos["project"],
            ref="v5",
            templates={r: setup.releases[r] for r in ("v4", "v5")},
            data={},
            worker_type=worker,
        )
        yield RemovalUpdate(setup, recording)


@pytest.mark.xdist_group("mechanics-removal")
class TestEachCopyRendersItsOwnRelease:
    """S12 control: what reaches the old copy, and which view each copy renders."""

    def test_old_copy_renders_from_the_answers_file_not_data(
        self, removal: RemovalUpdate
    ) -> None:
        """S12 control: with data={} the old copy still renders the recorded answer.

        Copier builds the old copy's answers from the layer's answers file,
        so nothing forced through ``data`` reaches it.
        """
        assert removal.recording.copies["old_copy"][LICENSE_FILE] == (
            "license=Apache-2.0\nrelease=v4\n"
        )

    def test_each_render_builds_its_template_from_its_own_refs_view(
        self, removal: RemovalUpdate
    ) -> None:
        """S12: Copier sets each rebuilt worker's ref; each builds that ref's view.

        The update builds a template for its checks, the old copy at the
        recorded v4, the in-place render and the new copy at the target v5.
        """
        assert removal.recording.builds == [
            ("in_place", "v5"),
            ("old_copy", "v4"),
            ("in_place", "v5"),
            ("new_copy", "v5"),
        ]


def test_forced_data_never_reaches_the_old_copy(tmp_path: Path) -> None:
    """Data forced into an update renders in place and in the new copy only.

    Forcing description 'FORCED' over the recorded one, the old copy's
    pyproject.toml still renders the recorded description. This checks the
    S12 control's reading directly; no probe log covers it.
    """
    setup = compose_license_project(tmp_path)
    worker, recording = recording_worker(["pyproject.toml"])
    data = {**recorded_answers(setup.project, "project"), "description": "FORCED"}
    update_layer(
        setup.project,
        root="streamlit",
        layer="project",
        source=setup.repos["project"],
        ref="v5",
        templates={r: setup.releases[r] for r in ("v4", "v5")},
        data=data,
        worker_type=worker,
    )
    descriptions = {
        role: next(
            line
            for line in (copy[name] or "").splitlines()
            if line.startswith("description")
        )
        for role, copy in recording.copies.items()
        for name in ("pyproject.toml",)
    }

    assert descriptions == {
        "old_copy": 'description = "Probe description"',
        "new_copy": 'description = "FORCED"',
    }


# ------------------------------------------------------------------ own answers


def test_layers_own_recorded_answer_beats_its_ancestors(tmp_path: Path) -> None:
    """The scoped data lays the layer's own answers over its ancestors'.

    With project recording author_name 'Ada Probe' and streamlit 'Own Name',
    updating streamlit keeps 'Own Name'. This checks the harness's layering
    rule through Copier's recording; no probe log covers it.
    """
    releases = build_releases(tmp_path, ("v1", "v2"))
    repos = build_repos(tmp_path, releases)
    project = tmp_path / "probe-app"
    compose_project("streamlit", project, ANSWERS, releases["v1"])
    make_git_project(project, repos, "v1")
    substitute(
        project / ".copier-answers.streamlit.yml",
        "author_name: Ada Probe\n",
        "author_name: Own Name\n",
    )
    commit_all(project, "streamlit's answer diverges from project's")
    update_layer(
        project,
        root="streamlit",
        layer="streamlit",
        source=repos["streamlit"],
        ref="v2",
        templates=releases,
    )

    assert {
        layer: recorded_answers(project, layer)["author_name"]
        for layer in ("project", "streamlit")
    } == {"project": "Ada Probe", "streamlit": "Own Name"}


# ------------------------------------------------------------------ S16

TASK = """
  - - "{{ _copier_python }}"
    - -c
    - |
      import json, os, sys
      rec = {"layer": sys.argv[1], "answers_file": sys.argv[2], "cwd": os.getcwd(),
             "operation": os.environ.get("COPIER_OPERATION")}
      with open(sys.argv[3], "a", encoding="utf-8") as fh:
          fh.write(json.dumps(rec) + "\\n")
      with open("task-marker.txt", "a", encoding="utf-8") as fh:
          fh.write(sys.argv[1] + "\\n")
    - LAYER
    - "{{ _copier_conf.answers_file }}"
    - LOGPATH
"""
BUNDLED_TASKS = '_tasks:\n  -  ["{{ _copier_python }}", _scripts/post_generation.py]\n'


class TaskRun(NamedTuple):
    """One run of a marker task: which layer's task, in which context, where."""

    layer: str
    answers_file: str
    operation: str
    where: str


class TaskWalk(NamedTuple):
    """Task runs at compose and per layer update, and the marker file after."""

    compose: list[TaskRun]
    updates: dict[str, list[TaskRun]]
    marker: list[str]


def _read_runs(log: Path, project: Path) -> list[TaskRun]:
    """Read and clear the task log, naming each run's working directory."""
    runs: list[TaskRun] = []
    for line in log.read_text(encoding="utf-8").splitlines():
        record: dict[str, Any] = json.loads(line)
        cwd = Path(record["cwd"])
        where = next(
            (r for r in ("old_copy", "new_copy") if r in cwd.name),
            "project" if cwd == project else str(cwd),
        )
        runs.append(
            TaskRun(record["layer"], record["answers_file"], record["operation"], where)
        )
    log.unlink()
    return runs


@pytest.fixture(scope="module")
def task_walk(tmp_path_factory: pytest.TempPathFactory) -> Iterator[TaskWalk]:
    """Give each layer a marker task, compose with tasks, then update both layers."""
    root = tmp_path_factory.mktemp("tasks")
    log = root / "tasklog.jsonl"

    def marker_tasks(ref: str, release: Path) -> None:
        def task(layer: str) -> str:
            return TASK.replace("LAYER", layer).replace("LOGPATH", log.as_posix())

        substitute(
            release / "project" / "copier.yml",
            BUNDLED_TASKS,
            "_tasks:" + task("project"),
        )
        append(release / "streamlit" / "copier.yml", "\n_tasks:" + task("streamlit"))
        write(release / "project" / "project_own.txt.jinja", f"release={ref}\n")

    with temp_dir_inside(root):
        releases = build_releases(root, ("v1", "v2"), marker_tasks)
        repos = build_repos(root, releases)
        project = root / "composed" / "probe-app"
        compose_project("streamlit", project, ANSWERS, releases["v1"], skip_tasks=False)
        compose_runs = _read_runs(log, project)
        make_git_project(project, repos, "v1")
        add_user_line(project / "README.md")
        updates: dict[str, list[TaskRun]] = {}
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
            updates[layer] = _read_runs(log, project)
            commit_all(project, f"update {layer} to v2")
        yield TaskWalk(compose_runs, updates, lines(project / "task-marker.txt"))


@pytest.mark.xdist_group("mechanics-tasks")
class TestTasks:
    """S16: where each layer's tasks run at compose and at update."""

    def test_compose_runs_every_layers_task_once_in_the_final_layers_context(
        self, task_walk: TaskWalk
    ) -> None:
        """S16: the merged tasks run once each, in the destination, on the final layer.

        Project's task renders `_copier_conf.answers_file` as streamlit's,
        because the merged tasks render in the final layer's context.
        """
        assert task_walk.compose == [
            TaskRun("project", ".copier-answers.streamlit.yml", "copy", "project"),
            TaskRun("streamlit", ".copier-answers.streamlit.yml", "copy", "project"),
        ]

    @pytest.mark.parametrize("layer", ["project", "streamlit"])
    def test_update_runs_the_layers_own_task_in_each_of_copiers_renders(
        self, task_walk: TaskWalk, layer: str
    ) -> None:
        """S16: a layer's update runs only its own task, three times.

        Copier runs it in the old copy, in place and in the new copy.
        """
        answers_file = f".copier-answers.{layer}.yml"

        assert task_walk.updates[layer] == [
            TaskRun(layer, answers_file, "update", where)
            for where in ("old_copy", "project", "new_copy")
        ]

    def test_in_place_task_output_is_undone_by_the_merge(
        self, task_walk: TaskWalk
    ) -> None:
        """S16: the marker lines the in-place tasks append do not survive the update."""
        assert task_walk.marker == ["project", "streamlit"]


# ------------------------------------------------------------------ S20


class ConflictUpdate(NamedTuple):
    """Streamlit updated to v2 over a user edit of the line v2 changes."""

    project: Path
    raised: BaseException | None


@pytest.fixture(scope="module")
def conflict(tmp_path_factory: pytest.TempPathFactory) -> Iterator[ConflictUpdate]:
    """Edit the README title the next release rewrites, then update streamlit."""
    root = tmp_path_factory.mktemp("conflict")

    def retitle(ref: str, release: Path) -> None:
        if ref == "v2":
            substitute(
                release / "streamlit" / "README.md.jinja",
                "# {{ project_name }}\n",
                "# {{ project_name }} (release v2)\n",
            )

    with temp_dir_inside(root):
        releases = build_releases(root, ("v1", "v2"), retitle)
        repos = build_repos(root, releases)
        project = root / "probe-app"
        compose_project("streamlit", project, ANSWERS, releases["v1"])
        make_git_project(project, repos, "v1")
        substitute(project / "README.md", "# Probe App\n", "# Probe App (user fork)\n")
        commit_all(project, "user edits the title line")
        raised: BaseException | None = None
        try:
            update_layer(
                project,
                root="streamlit",
                layer="streamlit",
                source=repos["streamlit"],
                ref="v2",
                templates=releases,
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
        """S20: README opens with inline markers around the user's and v2's title."""
        assert lines(conflict.project / "README.md")[:5] == [
            "<<<<<<< before updating",
            "# Probe App (user fork)",
            "=======",
            "# Probe App (release v2)",
            ">>>>>>> after updating",
        ]

    def test_conflict_is_visible_to_git_as_unmerged(
        self, conflict: ConflictUpdate
    ) -> None:
        """S20: git reports README unmerged, with base, ours and theirs staged."""
        stages = [
            line.split()[2]
            for line in git(
                conflict.project, "ls-files", "--stage", "README.md"
            ).splitlines()
        ]

        assert (git(conflict.project, "status", "--short").splitlines(), stages) == (
            [" M .copier-answers.streamlit.yml", "UU README.md"],
            ["1", "2", "3"],
        )

    def test_conflict_leaves_no_reject_file(self, conflict: ConflictUpdate) -> None:
        """S20: the inline conflict mode leaves no .rej file behind."""
        assert merge_state(conflict.project).rejects == []
