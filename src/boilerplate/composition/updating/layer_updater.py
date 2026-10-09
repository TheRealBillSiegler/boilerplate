"""Update one layer of a composed project with Copier."""

from pathlib import Path
from typing import Any

from boilerplate.composition.updating.layer_release import LayerRelease
from boilerplate.composition.updating.recorded_answers import (
    read_recorded_answers_by_layer,
)
from boilerplate.composition.updating.step_inputs import StepInputs
from boilerplate.composition.updating.update_data import (
    build_step_data,
    declaring_ancestors_answers,
)
from boilerplate.composition.updating.update_options import UpdateOptions
from boilerplate.composition.updating.update_views import UpdateViews
from boilerplate.project_state.answers_file import answers_file_name


def update_layer(
    project: Path,
    release: LayerRelease,
    views: UpdateViews,
    inputs: StepInputs,
    options: UpdateOptions | None = None,
) -> dict[str, Any]:
    """Update one layer of a composed project to `release` under two views.

    Copier renders the update's old copy at the recorded release and its new
    copy and the project in place at the target release. The old copy renders
    under `views.old`, the other two under `views.target`; the two differ when
    the layer's ancestors move, even if the layer's own ref does not.

    Copier reads the layer's own questions from the layer's own answers file;
    the step passes as data only the answers the declaring ancestors record,
    read from their answers files when the step starts, and the values given
    to it (``build_step_data``).

    Copier builds the old copy from the layer's own answers file alone, so a
    file a hand-run vanilla update trimmed would render the ancestors'
    questions at their defaults. The worker fills each key that file lacks
    from the answers the declaring layer recorded when the walk began
    (``inputs.walk_answers``), so a change an ancestor's step makes in the same
    walk stays out of the merge base. The in-place render then records the full
    answers again.

    The step grants Copier's ``unsafe``, its permission to load extensions and
    run tasks and migrations, only when ``views.unsafe_for`` says Copier's own
    check would flag the step: the policy compose follows with
    ``grants_unsafe``, so a layer that loads and runs nothing keeps Copier's
    consent gate. The grant is no wider than that check, because ``unsafe`` also
    switches off Copier's check that a render stays inside the project. It
    depends on `options` for one case: the target release's tasks count only
    when the step does not skip them.

    Args:
        project: The composed project, a git repository with a clean tree.
        release: The layer to update and the release to move it to.
        views: The view of the layer and its ancestors at the recorded
            releases and at the target releases, and whether they need the
            ``unsafe`` grant.
        inputs: The values the user supplies and the secrets given earlier in
            the same update, as data for the questions in the layer's scope,
            and every layer's recorded answers as the walk began.
        options: How the update runs; the defaults skip the layer's tasks,
            silence Copier and take every question's default without
            prompting.

    Returns:
        The secret answers the step ended with, for the walk to carry to the
        next step.

    Raises:
        RecordedAnswerRejectedError: If a non-interactive step finds a recorded
            answer of the layer that the target view rejects.
        UnsafeTemplateError: If the layer's releases hold a feature Copier
            refuses without the grant and ``views.unsafe_for`` is false.
    """
    options = options or UpdateOptions()
    recorded_by_layer = read_recorded_answers_by_layer(project)
    data = build_step_data(
        layer=release.layer,
        declared_by=views.target.declared_by,
        recorded_by_layer=recorded_by_layer,
        supplied=inputs.supplied,
        secrets=inputs.secrets,
    )
    old_copy_fill = declaring_ancestors_answers(
        layer=release.layer,
        declared_by=views.old.declared_by,
        recorded_by_layer=inputs.walk_answers,
    )
    with options.worker_type(  # pyright: ignore[reportCallIssue, reportGeneralTypeIssues]
        src_path=release.source,
        dst_path=project,
        answers_file=Path(answers_file_name(release.layer)),
        data=data,
        vcs_ref=release.ref,
        defaults=not options.interactive,
        skip_answered=options.skip_answered,
        overwrite=True,
        quiet=options.quiet,
        unsafe=views.unsafe_for(skip_tasks=options.skip_tasks),
        skip_tasks=options.skip_tasks,
        layer=release.layer,
        old_view=views.old,
        target_view=views.target,
        old_copy_fill=old_copy_fill,
    ) as worker:
        worker.run_update()
        return {
            name: worker.answers.user[name]
            for name in worker.template.secret_questions
            if name in worker.answers.user
        }
