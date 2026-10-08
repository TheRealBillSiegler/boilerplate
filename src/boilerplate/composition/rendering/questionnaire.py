"""Ask a composition's merged questionnaire once."""
# Spec: docs/design/04-composition-engine.md §Render Behavior

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from boilerplate.composition.models.composition import Composition
from boilerplate.composition.rendering.models.merged_template import MergedTemplate
from boilerplate.composition.rendering.questionnaire_answers import (
    QuestionnaireAnswers,
)
from boilerplate.composition.rendering.worker_options import WorkerOptions
from boilerplate.composition.rendering.worker_session import worker_session
from boilerplate.composition.views import build_layer_view, view_config


def ask_questionnaire(
    composition: Composition,
    *,
    destination: Path,
    data: Mapping[str, Any],
    user_defaults: Mapping[str, Any],
    defaults: bool,
) -> QuestionnaireAnswers:
    """Ask the full merged questionnaire of `composition` in a single pass.

    The first layer's Worker asks every question of the full merged schema, so
    the user is prompted once. It writes no file; each layer then renders under
    its own scoped view with these answers as data.

    Args:
        composition: The composition whose questions are asked.
        destination: The project directory, whose answers file the first layer
            reads for the previous answers that pre-fill a prompt.
        data: Copier's forced `data` channel: answers taken as-is, never asked.
        user_defaults: Overridable pre-fills for the prompts.
        defaults: Whether to accept every default instead of prompting.

    Returns:
        The pass's answers.

    Raises:
        UserCancelledError: If the user cancels a prompt.
        InteractiveRenderFailedError: If the environment cannot host the prompt.
    """
    view = build_layer_view(composition)
    first = composition.layers[0]
    template = MergedTemplate(
        str(first.path), dict(view.questions), view_config(view, skip_if_exists=[])
    )
    options: WorkerOptions = {
        "src_path": str(first.path),
        "dst_path": destination,
        "data": dict(data),
        "user_defaults": dict(user_defaults),
        "defaults": defaults,
        "unsafe": bool(template.jinja_extensions),
        "quiet": True,
    }
    with worker_session(options, template, view) as worker:
        worker._ask()  # pyright: ignore[reportPrivateUsage]
        return QuestionnaireAnswers(
            dict(worker.answers.user),
            dict(worker.answers.metadata),
            frozenset(worker.answers.hidden),
        )


__all__ = ["ask_questionnaire"]
