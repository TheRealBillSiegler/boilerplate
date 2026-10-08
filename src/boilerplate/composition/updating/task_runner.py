"""Run the composition's accumulated tasks once, after the update walk."""
# Spec: docs/design/04-composition-engine.md §Safe Update

from pathlib import Path

from boilerplate.composition.updating.layer_release import LayerRelease
from boilerplate.composition.updating.task_run import TaskRun
from boilerplate.composition.updating.update_options import UpdateOptions
from boilerplate.composition.views import LayerView


def run_update_tasks(
    project: Path,
    release: LayerRelease,
    view: LayerView,
    work: TaskRun,
    options: UpdateOptions | None = None,
) -> None:
    """Run the composition's tasks once in `project` as Copier's ``update`` operation.

    Every render of the walk skips tasks; this is the one run, against the
    finished project, as compose does at creation. It goes through the same
    worker as the walk, over the root layer's view at the target releases, with
    the root layer's recorded answers: the root's answers file records every
    answer of the composition except the secrets, which the walk carried in
    memory and passes here.

    Args:
        project: The updated project, in the user's checkout.
        release: The root layer and the release it was updated to.
        view: The root layer's view at the target releases.
        work: The composition's accumulated tasks and the secret answers the
            walk asked, for tasks that use them.
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
        worker.run_tasks()
