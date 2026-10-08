"""The answers an update of one layer forces on Copier.

The rule is pure: it takes the answers the project records and the answers a
questionnaire pass produced, and does no I/O of its own.
"""

from collections.abc import Collection, Mapping, Sequence
from typing import Any


def layered_recorded_answers(
    recorded_by_layer: Mapping[str, Mapping[str, Any]], chain: Sequence[str]
) -> dict[str, Any]:
    """Merge the recorded answers of `chain`, later layers over earlier ones.

    Args:
        recorded_by_layer: Each layer's recorded answers, keyed by layer name.
        chain: The layers whose answers apply, ancestors first and the layer
            being updated last; a layer with no recorded answers adds none.

    Returns:
        The merged recorded answers.

    Examples:
        The layer's own answer beats its ancestor's:

        >>> layered_recorded_answers(
        ...     {"core": {"author": "Ada", "port": 80}, "service": {"author": "Bo"}},
        ...     ["core", "service"],
        ... )
        {'author': 'Bo', 'port': 80}
    """
    merged: dict[str, Any] = {}
    for layer in chain:
        merged.update(recorded_by_layer.get(layer, {}))
    return merged


def build_update_data(
    *,
    recorded_by_layer: Mapping[str, Mapping[str, Any]],
    chain: Sequence[str],
    asked_user: Mapping[str, Any],
    asked_hidden: Collection[str],
    view_questions: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the forced answers an update of a layer passes to Copier.

    The recorded answers are the ancestors' in chain order with the layer's own
    laid on top. The questionnaire pass answers what the layer's view asks and
    those answers do not record, so a question added since the recorded release
    takes the pass's answer; a hidden question is never taken from it.

    Args:
        recorded_by_layer: Each layer's recorded answers, keyed by layer name.
        chain: The layers whose answers apply, ancestors first and the layer
            being updated last.
        asked_user: Every question's answer from the questionnaire pass.
        asked_hidden: Names of the questions the pass never showed.
        view_questions: The questions the layer's view asks, keyed by name.

    Returns:
        The pass's answers for unrecorded questions, with the recorded answers
        on top.

    Examples:
        A new question takes the pass's answer; a recorded one keeps its value:

        >>> build_update_data(
        ...     recorded_by_layer={"core": {"port": 80}},
        ...     chain=["core"],
        ...     asked_user={"port": 8080, "license": "MIT", "slug": "x"},
        ...     asked_hidden={"slug"},
        ...     view_questions={"port": {}, "license": {}, "slug": {}},
        ... )
        {'license': 'MIT', 'port': 80}
    """
    recorded = layered_recorded_answers(recorded_by_layer, chain)
    unanswered = {
        k: v
        for k, v in asked_user.items()
        if k in view_questions and k not in recorded and k not in asked_hidden
    }
    return {**unanswered, **recorded}
