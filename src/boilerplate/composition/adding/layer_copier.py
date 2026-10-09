"""Copy one new layer into a project with Copier."""

from pathlib import Path
from typing import Any

from boilerplate.composition.updating.layer_release import LayerRelease
from boilerplate.composition.updating.step_inputs import StepInputs
from boilerplate.composition.updating.update_data import build_step_data
from boilerplate.composition.updating.update_options import UpdateOptions
from boilerplate.composition.views import LayerView
from boilerplate.project_state.answers_file import answers_file_name


def copy_layer(
    project: Path,
    release: LayerRelease,
    view: LayerView,
    inputs: StepInputs,
    options: UpdateOptions | None = None,
) -> dict[str, Any]:
    """Copy the layer at `release` into `project` under `view`.

    The render is what one more by-hand ``copier copy`` of the layer with its own
    answers file makes: a file the layer's ``_skip_if_exists`` lists keeps the
    content it has, and any other file another layer rendered is overwritten.
    Copier asks the layer's own questions; the step passes as data only the
    answers the declaring ancestors record, taken from ``inputs.walk_answers``,
    and the values given to it (``build_step_data``).

    Args:
        project: The project, a git repository with a clean tree.
        release: The layer to add and the release to add it at.
        view: The view of the layer and its ancestors, with each question's
            definition taken from the merged schema of the project's layers plus
            the new one.
        inputs: The values the user supplies, as data for the questions in the
            layer's scope, and each layer's answers as they stood when the add
            began.
        options: How the copy runs; the defaults skip the layer's tasks, silence
            Copier and take every question's default without prompting.

    Returns:
        The secret answers the copy ended with, for the task run.
    """
    options = options or UpdateOptions()
    data = build_step_data(
        layer=release.layer,
        declared_by=view.declared_by,
        recorded_by_layer=inputs.walk_answers,
        supplied=inputs.supplied,
        secrets=inputs.secrets,
    )
    with options.worker_type(  # pyright: ignore[reportCallIssue, reportGeneralTypeIssues]
        src_path=release.source,
        dst_path=project,
        answers_file=Path(answers_file_name(release.layer)),
        data=data,
        vcs_ref=release.ref,
        defaults=not options.interactive,
        overwrite=True,
        quiet=options.quiet,
        unsafe=True,
        skip_tasks=options.skip_tasks,
        layer=release.layer,
        old_view=view,
        target_view=view,
    ) as worker:
        worker.run_copy()
        return {
            name: worker.answers.user[name]
            for name in worker.template.secret_questions
            if name in worker.answers.user
        }
