"""``LayerAdder`` runs the added layer's own tasks once, after the copy back.

A by-hand ``copier copy`` of the layer runs the layer's tasks under the ``copy``
operation, and design 06 §Adding a layer has the add run them once against the
finished project. A task that fails is handled as an update's is: a caller that
cannot ask keeps the files and writes the lock; a caller that asks may undo.
"""

from pathlib import Path

import pytest

from boilerplate.common.exceptions import UpdateTaskFailedError
from boilerplate.composition.adding import AddRequest, AddStatus, LayerAdder
from boilerplate.composition.updating.failed_task import FailedTask
from boilerplate.composition.updating.task_failure_choice import TaskFailureChoice
from boilerplate.models import MigrationStatus
from boilerplate.project_state.lock_file import LOCK_FILE_NAME, read_lock
from boilerplate.project_state.migrations_file import MIGRATIONS_FILE, read_migrations
from tests.boilerplate.templates.conftest import git
from tests.integration.boilerplate.composition.adding.layers import build_layer
from tests.integration.boilerplate.composition.family import Family
from tests.integration.boilerplate.composition.scenarios.builders import (
    answers_file,
    compose_locked_family,
    lines,
    tree,
)

PYTHON = '"{{ _copier_python }}"'
OPERATION_TASK = """\
_tasks:
  - command:
      - "{{ _copier_python }}"
      - -c
      - "print('{{ _copier_operation }}', file=open('.tasked-marker', 'a', encoding='utf-8'))"
"""
FAILING_TASK = """\
_tasks:
  - command:
      - "{{ _copier_python }}"
      - -c
      - "raise SystemExit(3)"
"""
SECRET_TASK = """\
deploy_token:
  type: str
  secret: true
  default: ""

_tasks:
  - command:
      - "{{ _copier_python }}"
      - -c
      - "print('{{ deploy_token }}', file=open('.token-marker', 'a', encoding='utf-8'))"
"""


@pytest.fixture
def project(family: Family, tmp_path: Path) -> Path:
    """Compose core on its own, lock it and commit."""
    return compose_locked_family(family, tmp_path, "core", {"core": "1.0.0"})


def request(project: Path, name: str, **options: bool) -> AddRequest:
    """Build the request that adds the one-off layer `name` built beside `project`."""
    return AddRequest(
        name=name, source=(project.parent / "repos" / name).as_posix(), **options
    )


def undo(_failed: FailedTask) -> TaskFailureChoice:
    """Choose to undo the add, as a user at a prompt may."""
    return TaskFailureChoice.UNDO


class TestOwnTasks:
    def test_the_layers_task_runs_once_under_the_copy_operation(
        self, project: Path
    ) -> None:
        build_layer(project.parent, "tasked", copier=OPERATION_TASK)

        LayerAdder().add(project, request(project, "tasked"))

        assert lines(project / ".tasked-marker") == ["copy"]

    def test_the_ancestors_tasks_do_not_run_again(self, project: Path) -> None:
        build_layer(project.parent, "tasked", copier=OPERATION_TASK)

        LayerAdder().add(project, request(project, "tasked"))

        assert not (project / ".core-task-marker").exists()

    def test_no_tasks_skips_the_layers_tasks(self, project: Path) -> None:
        build_layer(project.parent, "tasked", copier=OPERATION_TASK)

        LayerAdder().add(project, request(project, "tasked", no_tasks=True))

        assert not (project / ".tasked-marker").exists()

    def test_a_secret_answer_reaches_the_task_but_not_the_answers_file(
        self, project: Path
    ) -> None:
        build_layer(project.parent, "secretive", copier=SECRET_TASK)
        asked = AddRequest(
            name="secretive",
            source=(project.parent / "repos" / "secretive").as_posix(),
            supplied={"deploy_token": "s3cret"},
        )

        LayerAdder().add(project, asked)

        assert (
            lines(project / ".token-marker"),
            "deploy_token" in answers_file(project, "secretive"),
        ) == (["s3cret"], False)


class TestAFailedTask:
    def test_a_caller_that_cannot_ask_keeps_the_files_and_raises(
        self, project: Path
    ) -> None:
        build_layer(project.parent, "failing", copier=FAILING_TASK)

        with pytest.raises(UpdateTaskFailedError) as stop:
            LayerAdder().add(project, request(project, "failing"))

        assert stop.value.remediation is not None
        assert "Run it by hand" in stop.value.remediation

    def test_the_kept_add_still_writes_the_lock(self, project: Path) -> None:
        build_layer(project.parent, "failing", copier=FAILING_TASK)
        with pytest.raises(UpdateTaskFailedError):
            LayerAdder().add(project, request(project, "failing"))

        assert [entry.name for entry in read_lock(project).layers] == [
            "core",
            "failing",
        ]

    def test_the_kept_add_is_recorded_as_failed(self, project: Path) -> None:
        build_layer(project.parent, "failing", copier=FAILING_TASK)
        with pytest.raises(UpdateTaskFailedError):
            LayerAdder().add(project, request(project, "failing"))

        (record,) = read_migrations(project)

        assert (record.status, record.to_version) == (
            MigrationStatus.FAILED,
            "failing@1.0.0",
        )

    def test_undoing_returns_the_checkout_to_its_start(self, project: Path) -> None:
        build_layer(project.parent, "failing", copier=FAILING_TASK)
        before = (tree(project), (project / LOCK_FILE_NAME).read_bytes())

        outcome = LayerAdder(on_task_failure=undo).add(
            project, request(project, "failing")
        )

        assert (
            outcome.status,
            tree(project),
            (project / LOCK_FILE_NAME).read_bytes(),
            git(project, "status", "--porcelain"),
            (project / MIGRATIONS_FILE).exists(),
        ) == (AddStatus.UNDONE, before[0], before[1], "", False)
