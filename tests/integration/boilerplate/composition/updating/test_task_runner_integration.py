"""The task run after an update's walk or an add, on a project of the made-up family."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any, Literal

import pytest

from boilerplate.composition.updating import LayerRelease, UpdateOptions
from boilerplate.composition.updating.release_ref import ReleaseRef
from boilerplate.composition.updating.release_views import ReleaseViews
from boilerplate.composition.updating.task_run import TaskRun
from boilerplate.composition.updating.task_runner import run_tasks
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
OPERATIONS: tuple[Literal["copy", "update"], ...] = ("copy", "update")


def write_line(file: str, text: str) -> dict[str, Any]:
    """Return a task that appends `text` to `file`, rendered by Copier first."""
    code = f"print('{text}', file=open('{file}', 'a', encoding='utf-8'))"
    return {"command": [PYTHON, "-c", code]}


def only_under(operation: str, file: str) -> dict[str, Any]:
    """Return a task that writes `file` only under Copier's `operation`."""
    return {
        **write_line(file, "ran"),
        "when": f"{{{{ _copier_operation == '{operation}' }}}}",
    }


class Run:
    """A composed family project and what it takes to run its tasks."""

    def __init__(self, family: Family, project: Path, views: ReleaseViews) -> None:
        self.project = project
        self.release = LayerRelease(
            layer="service", source=family.repos["service"].as_posix(), ref="1.0.0"
        )
        self.releases = {
            layer: ReleaseRef(source=family.repos[layer].as_posix(), ref=tag)
            for layer, tag in TAGS.items()
        }
        self.views = views

    def tasks(self) -> list[Any]:
        """Return the composition's accumulated task list."""
        return list(self.views.tasks(self.releases))

    def run(
        self,
        tasks: list[Any] | None = None,
        secrets: dict[str, Any] | None = None,
        operation: Literal["copy", "update"] = "update",
    ) -> None:
        """Run `tasks` (the composition's by default) in the project."""
        run_tasks(
            self.project,
            self.release,
            self.views.step_view("service", self.releases),
            TaskRun(
                operation=operation,
                tasks=self.tasks() if tasks is None else tasks,
                secrets=secrets or {},
            ),
            options=UpdateOptions(),
        )


@pytest.fixture
def run(family: Family, tmp_path: Path) -> Iterator[Run]:
    """Compose the project without tasks, so only the run under test executes them."""
    project = compose_family(family, tmp_path, "service", TAGS)
    with ReleaseCheckouts() as checkouts:
        views = ReleaseViews(checkouts, workdir=tmp_path / "views")
        yield Run(family, project, views)


class TestRunTasks:
    def test_runs_the_composition_tasks_in_the_project(self, run: Run) -> None:
        """Execute core's task once, against the project folder."""
        run.run()

        assert lines(run.project / ".core-task-marker") == ["core task ran"]

    @pytest.mark.parametrize("operation", OPERATIONS)
    def test_tasks_run_under_the_given_operation(
        self, run: Run, operation: Literal["copy", "update"]
    ) -> None:
        """Give each task ``_copier_operation`` as the operation the caller names.

        An update's tasks run as ``update`` (ADR-014); an add's run as ``copy``,
        as at compose (design 06 §Adding a layer).
        """
        run.run(
            [write_line("operation.txt", "{{ _copier_operation }}")], None, operation
        )

        assert lines(run.project / "operation.txt") == [operation]

    @pytest.mark.parametrize("operation", OPERATIONS)
    def test_a_task_guarded_by_the_other_operation_is_skipped(
        self, run: Run, operation: Literal["copy", "update"]
    ) -> None:
        """Let a template guard a task with the operation, as Copier does."""
        other = "update" if operation == "copy" else "copy"

        run.run([only_under(other, "other.txt")], None, operation)

        assert not (run.project / "other.txt").exists()

    @pytest.mark.parametrize("operation", OPERATIONS)
    def test_tasks_run_in_copiers_tasks_phase(
        self, run: Run, operation: Literal["copy", "update"]
    ) -> None:
        """Let a template guard a task with the phase, as under Copier's own run."""
        tasks_only = {
            **write_line("phase.txt", "{{ _copier_phase }}"),
            "when": "{{ _copier_phase == 'tasks' }}",
        }

        run.run([tasks_only], None, operation)

        assert lines(run.project / "phase.txt") == ["tasks"]

    def test_a_task_sees_a_secret_given_to_the_run(self, run: Run) -> None:
        """Pass the secrets the run asked, which no answers file records."""
        run.run(
            [write_line("token.txt", "{{ api_token }}")], secrets={"api_token": "s3"}
        )

        assert lines(run.project / "token.txt") == ["s3"]

    def test_a_failing_task_raises_copiers_task_error(self, run: Run) -> None:
        """Surface the failed command for the caller to name."""
        failing = {"command": [PYTHON, "-c", "raise SystemExit(3)"]}

        with pytest.raises(TaskError) as raised:
            run.run([failing])

        assert raised.value.returncode == 3
