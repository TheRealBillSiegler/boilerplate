"""Update one layer of a composed project with Copier."""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from boilerplate.composition.updating.layer_release import LayerRelease
from boilerplate.composition.updating.update_options import UpdateOptions
from boilerplate.composition.updating.update_views import UpdateViews


def update_layer(
    project: Path,
    release: LayerRelease,
    views: UpdateViews,
    data: Mapping[str, Any],
    options: UpdateOptions | None = None,
) -> None:
    """Update one layer of a composed project to `release` under two views.

    Copier renders the update's old copy at the recorded release and its new
    copy and the project in place at the target release. The old copy renders
    under `views.old`, the other two under `views.target`; the two differ when
    the layer's ancestors move, even if the layer's own ref does not.

    Args:
        project: The composed project, a git repository with a clean tree.
        release: The layer to update and the release to move it to.
        views: The view of the layer and its ancestors at the recorded
            releases and at the target releases.
        data: Forced answers; ``{}`` is a vanilla ``copier update``, which
            reads only the answers file.
        options: How the update runs; the defaults skip the layer's tasks,
            silence Copier and take every question's default without
            prompting.
    """
    options = options or UpdateOptions()
    with options.worker_type(  # pyright: ignore[reportCallIssue, reportGeneralTypeIssues]
        src_path=str(release.source),
        dst_path=project,
        answers_file=Path(f".copier-answers.{release.layer}.yml"),
        data=dict(data),
        vcs_ref=release.ref,
        defaults=not options.interactive,
        skip_answered=options.skip_answered,
        overwrite=True,
        quiet=options.quiet,
        unsafe=True,
        skip_tasks=options.skip_tasks,
        layer=release.layer,
        old_view=views.old,
        target_view=views.target,
    ) as worker:
        worker.run_update()
