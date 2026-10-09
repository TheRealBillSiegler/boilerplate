"""Copy one new layer into a project with Copier."""

from pathlib import Path
from typing import Any

from boilerplate.composition.adding.add_plan import AddPlan
from boilerplate.composition.updating.step_inputs import StepInputs
from boilerplate.composition.updating.update_data import build_step_data
from boilerplate.composition.updating.update_options import UpdateOptions
from boilerplate.project_state.answers_file import answers_file_name


def copy_layer(
    project: Path,
    plan: AddPlan,
    inputs: StepInputs,
    options: UpdateOptions | None = None,
) -> dict[str, Any]:
    """Copy the layer `plan` adds into `project` under the plan's view.

    The render is what one more by-hand ``copier copy`` of the layer with its own
    answers file makes: a file the layer's ``_skip_if_exists`` lists keeps the
    content it has, and any other file another layer rendered is overwritten.
    Copier asks the layer's own questions; the step passes as data only the
    answers the declaring ancestors record, taken from ``inputs.walk_answers``,
    and the values given to it (``build_step_data``).

    The copy grants Copier's ``unsafe`` only when ``plan.unsafe_for`` says
    Copier's own check would flag it, so a layer that loads nothing keeps
    Copier's consent gate and its check that a render stays inside the project.
    A layer's tasks count only when the copy runs them.

    Args:
        project: The project, a git repository with a clean tree.
        plan: The add: the layer and the release to add it at, its view of the
            layer and its ancestors with each question defined by the merged
            schema of the project's layers plus the new one, and what decides
            the ``unsafe`` grant.
        inputs: The values the user supplies, as data for the questions in the
            layer's scope, and each layer's answers as they stood when the add
            began.
        options: How the copy runs; the defaults skip the layer's tasks, silence
            Copier and take every question's default without prompting.

    Returns:
        The secret answers the copy ended with, for the task run.
    """
    release = plan.release
    options = options or UpdateOptions()
    data = build_step_data(
        layer=release.layer,
        declared_by=plan.view.declared_by,
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
        unsafe=plan.unsafe_for(skip_tasks=options.skip_tasks),
        skip_tasks=options.skip_tasks,
        layer=release.layer,
        old_view=plan.view,
        target_view=plan.view,
    ) as worker:
        worker.run_copy()
        return {
            name: worker.answers.user[name]
            for name in worker.template.secret_questions
            if name in worker.answers.user
        }
