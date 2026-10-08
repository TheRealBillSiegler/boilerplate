"""Update one layer of a composed project with Copier."""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from boilerplate.composition.updating.layer_release import LayerRelease
from boilerplate.composition.updating.update_options import UpdateOptions
from boilerplate.composition.views import LayerView


def update_layer(
    project: Path,
    release: LayerRelease,
    views_by_ref: Mapping[str, LayerView],
    data: Mapping[str, Any],
    options: UpdateOptions | None = None,
) -> None:
    """Update one layer of a composed project to `release` under per-ref views.

    Copier renders the update's old copy at the recorded ref and its new copy
    and the project in place at the release's ref; each render builds its
    template from the view keyed by its own ref.

    Args:
        project: The composed project, a git repository with a clean tree.
        release: The layer to update and the release to move it to.
        views_by_ref: The view each render of the update uses, keyed by
            template ref; the recorded ref and the release's ref must both be
            keys.
        data: Forced answers; ``{}`` is a vanilla ``copier update``, which
            reads only the answers file.
        options: How the update runs; the defaults skip the layer's tasks and
            silence Copier.
    """
    options = options or UpdateOptions()
    with options.worker_type(  # pyright: ignore[reportCallIssue, reportGeneralTypeIssues]
        src_path=str(release.source),
        dst_path=project,
        answers_file=Path(f".copier-answers.{release.layer}.yml"),
        data=dict(data),
        vcs_ref=release.ref,
        defaults=True,
        overwrite=True,
        quiet=options.quiet,
        unsafe=True,
        skip_tasks=options.skip_tasks,
        views_by_ref=dict(views_by_ref),
    ) as worker:
        worker.run_update()
