"""Check that each layer's answers file records every answer its view asks for."""
# Spec: docs/design/04-composition-engine.md §Safe Update

from collections.abc import Collection, Mapping
from typing import Any

from boilerplate.common.exceptions import AnswersFileIncompleteError
from boilerplate.composition.views import LayerView

__all__ = ["check_answers_complete", "required_answer_keys"]


def _is_recorded(definition: Any) -> bool:  # noqa: ANN401
    """Return whether Copier records an answer for a question with `definition`.

    Copier leaves a secret question out of the answers file and records no
    answer for a question whose ``when`` hides it. A literal ``when: false`` is
    derived and always hidden; a ``when`` expression depends on other answers, so
    it cannot be judged without rendering and the question is not required.
    """
    if not isinstance(definition, Mapping):
        return True
    if definition.get("secret"):  # pyright: ignore[reportUnknownMemberType]
        return False
    return definition.get("when", True) is True  # pyright: ignore[reportUnknownMemberType]


def required_answer_keys(view: LayerView) -> tuple[str, ...]:
    """Return the keys a layer's answers file must record for `view`.

    Args:
        view: The layer's scoped view at the recorded versions.

    Returns:
        The non-secret, non-derived, unconditional question names, in the
        view's question order. Directives (``_``-prefixed keys) are not
        questions.

    Examples:
        >>> view = LayerView(
        ...     {"name": {}, "token": {"secret": True}, "slug": {"when": False}}, ()
        ... )
        >>> required_answer_keys(view)
        ('name',)
    """
    return tuple(
        name
        for name, definition in view.questions.items()
        if not name.startswith("_") and _is_recorded(definition)
    )


def check_answers_complete(
    views: Mapping[str, LayerView], recorded: Mapping[str, Collection[str]]
) -> None:
    """Stop the update when an answers file lacks a key its view asks for.

    The old copy reads only the layer's own answers file, so a file that lacks
    an ancestor's answers, as a hand-run vanilla update of the layer leaves it,
    renders the ancestor's questions at their defaults. This runs before any
    layer does.

    Args:
        views: Each layer's scoped view at the recorded versions, keyed by layer
            name in walk order.
        recorded: The keys each layer's answers file records, keyed by layer
            name; a layer with no entry has no answers file.

    Raises:
        AnswersFileIncompleteError: If any layer's file lacks a required key.
            The message names each such layer and its missing keys.
    """
    missing = {
        layer: tuple(
            key
            for key in required_answer_keys(view)
            if key not in recorded.get(layer, ())
        )
        for layer, view in views.items()
    }
    missing = {layer: keys for layer, keys in missing.items() if keys}
    if missing:
        lines = "\n".join(
            f"  {layer}: {', '.join(keys)}" for layer, keys in missing.items()
        )
        raise AnswersFileIncompleteError(
            "A layer's answers file lacks answers its questions need, as a "
            f"hand-run update of that layer leaves it:\n{lines}",
            missing=missing,
        )
