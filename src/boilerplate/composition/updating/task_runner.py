"""Run tasks once against a finished project, after an update's walk or an add."""
# Spec: docs/design/04-composition-engine.md §Safe Update

from pathlib import Path

from boilerplate.composition.updating.layer_release import LayerRelease
from boilerplate.composition.updating.task_run import TaskRun
from boilerplate.composition.updating.update_options import UpdateOptions
from boilerplate.composition.views import LayerView
from boilerplate.project_state.answers_file import answers_file_name


def run_tasks(
    project: Path,
    release: LayerRelease,
    view: LayerView,
    work: TaskRun,
    options: UpdateOptions | None = None,
) -> None:
    """Run `work`'s tasks once in `project` under the operation it names.

    Every render before this skips tasks; this is the one run, against the
    finished project, as compose does at creation. After an update it runs the
    composition's accumulated tasks under ``update``, over the root layer's
    view at the target releases, with the root's answers file, which records
    every answer of the composition except the secrets. After an add it runs
    the added layer's own tasks under ``copy``, as at compose, over that
    layer's view, with its answers file. Either way it goes through the same
    worker as the renders, and the secrets the run asked, which no answers file
    records, are passed here.

    Args:
        project: The finished project, in the user's checkout.
        release: The layer whose answers file the tasks read: the root after
            an update, the added layer after an add; at its new release.
        view: That layer's view at the releases the project moved to.
        work: The tasks, the Copier operation they run under, and the secret
            answers the run asked, for tasks that use them.
        options: How the run goes: ``quiet``, the worker class, and
            ``interactive`` and ``skip_answered``, which a rerun of a
            cut-off run sets so a secret the tasks use is asked again.

    Raises:
        TaskError: If a task exits non-zero; it names the command.
    """
    options = options or UpdateOptions()
    if not work.tasks:
        return
    with options.worker_type(  # pyright: ignore[reportCallIssue, reportGeneralTypeIssues]
        src_path=release.source,
        dst_path=project,
        answers_file=Path(answers_file_name(release.layer)),
        data=dict(work.secrets),
        vcs_ref=release.ref,
        defaults=not options.interactive,
        skip_answered=options.skip_answered,
        overwrite=True,
        quiet=options.quiet,
        unsafe=True,
        skip_tasks=False,
        layer=release.layer,
        old_view=view,
        target_view=view,
        tasks=tuple(work.tasks),
    ) as worker:
        worker.run_tasks(work.operation)
