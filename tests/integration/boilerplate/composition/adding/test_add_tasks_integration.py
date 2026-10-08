"""The task run that follows an add, on a composed project of the made-up family."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from boilerplate.composition.adding.task_runner import run_add_tasks
from boilerplate.composition.updating import LayerRelease
from boilerplate.composition.updating.release_ref import ReleaseRef
from boilerplate.composition.updating.release_views import ReleaseViews
from boilerplate.composition.updating.task_run import TaskRun
from boilerplate.integrations.copier_types import TaskError
from boilerplate.repository.release_checkouts import ReleaseCheckouts
from tests.integration.boilerplate.composition.family import Family
from tests.integration.boilerplate.composition.scenarios.builders import (
    compose_family,
    lines,
)

pytestmark = [pytest.mark.scenario]

TAGS = {"core": "1.0.0", "service": "1.0.0"}
PYTHON = "{{ _copier_python }}"


def write_line(file: str, text: str) -> dict[str, Any]:
    """Return a task that appends `text` to `file`, rendered by Copier first."""
    code = f"print('{text}', file=open('{file}', 'a', encoding='utf-8'))"
    return {"command": [PYTHON, "-c", code]}


class Run:
    """A composed family project and what it takes to run an added layer's tasks."""

    def __init__(self, family: Family, project: Path, views: ReleaseViews) -> None:
        self.project = project
        self.release = LayerRelease(
            layer="service", source=family.repos["service"], ref="1.0.0"
        )
        self.releases = {
            layer: ReleaseRef(source=family.repos[layer].as_posix(), ref=tag)
            for layer, tag in TAGS.items()
        }
        self.views = views

    def run(self, tasks: list[Any], secrets: dict[str, Any] | None = None) -> None:
        """Run `tasks` in the project, as the add of the service layer does."""
        run_add_tasks(
            self.project,
            self.release,
            self.views.step_view("service", self.releases),
            TaskRun(tasks=tasks, secrets=secrets or {}),
        )


@pytest.fixture
def run(family: Family, tmp_path: Path) -> Iterator[Run]:
    """Compose the project without tasks, so only the run under test executes them."""
    project = compose_family(family, tmp_path, "service", TAGS)
    with ReleaseCheckouts() as checkouts:
        views = ReleaseViews(checkouts, workdir=tmp_path / "views")
        yield Run(family, project, views)


class TestRunAddTasks:
    def test_runs_the_given_tasks_in_the_project(self, run: Run) -> None:
        """Execute the task once, against the project folder."""
        run.run([write_line("ran.txt", "ran")])

        assert lines(run.project / "ran.txt") == ["ran"]

    def test_tasks_run_under_the_copy_operation(self, run: Run) -> None:
        """Give each task ``_copier_operation == "copy"``, as a by-hand copy does."""
        run.run([write_line("operation.txt", "{{ _copier_operation }}")])

        assert lines(run.project / "operation.txt") == ["copy"]

    def test_an_update_only_task_is_skipped(self, run: Run) -> None:
        """Let a template guard a task with the operation, as Copier does."""
        update_only = {
            **write_line("update.txt", "updated"),
            "when": "{{ _copier_operation == 'update' }}",
        }

        run.run([update_only])

        assert not (run.project / "update.txt").exists()

    def test_a_task_sees_a_secret_given_to_the_run(self, run: Run) -> None:
        """Pass the secrets the copy asked, which no answers file records."""
        run.run([write_line("token.txt", "{{ api_token }}")], {"api_token": "s3"})

        assert lines(run.project / "token.txt") == ["s3"]

    def test_a_failing_task_raises_copiers_task_error(self, run: Run) -> None:
        """Name the command that exited non-zero."""
        failing = {"command": [PYTHON, "-c", "raise SystemExit(3)"]}

        with pytest.raises(TaskError) as stop:
            run.run([failing])

        assert stop.value.returncode == 3
