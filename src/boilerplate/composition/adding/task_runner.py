"""Run a newly added layer's tasks once, after the add."""
# Spec: docs/design/06-project-lifecycle.md §Part 2: Project Update

from pathlib import Path

from boilerplate.composition.updating.layer_release import LayerRelease
from boilerplate.composition.updating.task_run import TaskRun
from boilerplate.composition.updating.update_options import UpdateOptions
from boilerplate.composition.views import LayerView


def run_add_tasks(
    project: Path,
    release: LayerRelease,
    view: LayerView,
    work: TaskRun,
    options: UpdateOptions | None = None,
) -> None:
    """Run `work`'s tasks in `project` as a by-hand copy of the layer runs them.

    The copy that added the layer skipped its tasks; this is the one run, against
    the project with the layer's files in place. It goes through the same worker
    as the copy, over the layer's view, with the layer's answers file and the
    secret answers the copy asked.

    Args:
        project: The project holding the added layer, in the user's checkout.
        release: The added layer and the release it was added at.
        view: The layer's view at the releases it was added against.
        work: The layer's own tasks and the secret answers the copy asked, for
            tasks that use them.
        options: How the run goes; only ``quiet`` and the worker class apply.

    Raises:
        TaskError: If a task exits non-zero; it names the command.
    """
    options = options or UpdateOptions()
    if not work.tasks:
        return
    with options.worker_type(  # pyright: ignore[reportCallIssue, reportGeneralTypeIssues]
        src_path=str(release.source),
        dst_path=project,
        answers_file=Path(f".copier-answers.{release.layer}.yml"),
        data=dict(work.secrets),
        vcs_ref=release.ref,
        defaults=True,
        overwrite=True,
        quiet=options.quiet,
        unsafe=True,
        skip_tasks=False,
        layer=release.layer,
        old_view=view,
        target_view=view,
        tasks=tuple(work.tasks),
    ) as worker:
        worker.run_tasks("copy")
