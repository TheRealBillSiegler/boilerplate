"""The bundled setup task runs when Copier copies and never when it updates.

The project layer's post-generation script deletes its own `_scripts` folder
once it has run. Copier treats that deletion as intentional and never restores
the file, and an update runs every layer's tasks again, so an unguarded task
fails on every update. The layer guards it with Copier's mapping form and a
`when` on `_copier_operation` (docs/design/adr-014-deferred-task-execution.md
names the `when:` gate as the idiomatic one).

Two claims are pinned:

- The bundled composition declares the setup task creation-only.
- A `when` on a task survives Boilerplate's task pipeline, from `copier.yml`
  through the merge to Copier's own evaluation, on a copy and on an update.

A throwaway layer checks the second claim. Its task leaves a marker file outside
the project, because the bundled task needs `uv` and the network, and a marker
inside the project would be swept into the update's own diff. An unguarded
control shows the update test can see a task run.
"""

import sys
from pathlib import Path

import pytest
from jinja2 import Environment

from boilerplate.composition.tasks import normalize_tasks
from tests.boilerplate.templates.conftest import (
    build_layer_repo,
    commit_all,
    compose,
    compose_project,
    init_repo,
    rehome_layer,
    render,
    update_layer,
)

LAYER_NAME = "marker"
MARKER = "task-ran.txt"
OLD_TAG = "v0.1.0"
NEW_TAG = "v0.2.0"
ANSWERS_FILE = f".copier-answers.{LAYER_NAME}.yml"
ANSWERS_STUB = (
    "# Changes here will be overwritten by Copier; NEVER EDIT MANUALLY\n"
    "{{ _copier_answers|to_nice_yaml -}}\n"
)


def _write_marker_layer(
    templates_dir: Path, *, when: str, marker: Path, release: str = "1"
) -> Path:
    """Write a layer whose only task creates `marker` when it runs.

    Args:
        templates_dir: The directory to add the layer to.
        when: The task's `when` condition, a Jinja expression string.
        marker: The file the task creates; keep it outside the project.
        release: Text for the layer's README, so two releases differ.

    Returns:
        The layer's directory.
    """
    layer = templates_dir / LAYER_NAME
    layer.mkdir(parents=True)
    write_marker = f"open({str(marker)!r}, 'w').close()"
    (layer / "boilerplate.yml").write_text(
        f'schema_version: "1"\nname: {LAYER_NAME}\nversion: 0.1.0\n'
        "description: marker\n",
        encoding="utf-8",
    )
    (layer / "copier.yml").write_text(
        f"_answers_file: {ANSWERS_FILE}\n"
        "_tasks:\n"
        f"  - command: [{sys.executable!r}, '-c', {write_marker!r}]\n"
        f"    when: {when!r}\n",
        encoding="utf-8",
    )
    (layer / "{{_copier_conf.answers_file}}.jinja").write_text(
        ANSWERS_STUB, encoding="utf-8"
    )
    (layer / "README.md").write_text(f"marker layer {release}\n", encoding="utf-8")
    return layer


class TestBundledSetupTaskIsCreationOnly:
    @pytest.mark.parametrize("root", ["project", "streamlit"])
    @pytest.mark.parametrize(("operation", "runs"), [("copy", True), ("update", False)])
    def test_every_composed_task_runs_only_on_copy(
        self, root: str, operation: str, runs: bool
    ) -> None:
        tasks = normalize_tasks(compose(root).final)

        assert tasks, "the composition declares a setup task"
        for task in tasks:
            assert isinstance(task, dict), "a bare task has no condition to gate it"
            condition = Environment().from_string(str(task["when"]))
            assert (condition.render(_copier_operation=operation) == "True") is runs


class TestTaskConditionSurvivesTheRender:
    @pytest.mark.parametrize(
        ("when", "runs"),
        [
            ("{{ _copier_operation == 'copy' }}", True),
            ("{{ _copier_operation == 'update' }}", False),
        ],
        ids=["true-on-copy", "false-on-copy"],
    )
    def test_copy_runs_the_task_only_when_its_condition_holds(
        self, tmp_path: Path, when: str, runs: bool
    ) -> None:
        templates = tmp_path / "templates"
        marker = tmp_path / MARKER
        _write_marker_layer(templates, when=when, marker=marker)

        render(LAYER_NAME, tmp_path, skip_tasks=False, templates_dir=templates)

        assert marker.exists() is runs


@pytest.mark.slow
class TestTaskConditionSurvivesAnUpdate:
    @pytest.mark.parametrize(
        ("when", "runs"),
        [
            ("{{ _copier_operation == 'copy' }}", False),
            ("true", True),
        ],
        ids=["creation-only", "unguarded"],
    )
    def test_update_runs_the_task_only_when_its_condition_holds(
        self, tmp_path: Path, when: str, runs: bool
    ) -> None:
        marker = tmp_path / MARKER
        old = _write_marker_layer(tmp_path / "old", when=when, marker=marker)
        new = _write_marker_layer(
            tmp_path / "new", when=when, marker=marker, release="2"
        )
        repo = build_layer_repo(tmp_path / "repo", {OLD_TAG: old, NEW_TAG: new})
        project = tmp_path / "out"
        compose_project(LAYER_NAME, project, {}, tmp_path / "old")
        rehome_layer(project, layer=LAYER_NAME, source=repo, commit=OLD_TAG)
        init_repo(project)
        commit_all(project, "project at the first release")

        update_layer(
            project,
            root=LAYER_NAME,
            layer=LAYER_NAME,
            source=repo,
            ref=NEW_TAG,
            templates={OLD_TAG: tmp_path / "old", NEW_TAG: tmp_path / "new"},
            skip_tasks=False,
        )

        assert marker.exists() is runs
