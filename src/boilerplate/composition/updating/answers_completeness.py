"""Check that an answers file records every answer each layer's view asks for."""
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
        view's question order. A question is secret when it is marked
        ``secret: true`` or the view's ``_secret_questions`` names it.
        Directives (``_``-prefixed keys) are not questions.

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
        if not name.startswith("_")
        and name not in view.secret_questions
        and _is_recorded(definition)
    )


def check_answers_complete(
    views: Mapping[str, LayerView], recorded: Mapping[str, Collection[str]]
) -> None:
    """Stop the update when no answers file records a key a layer's view asks for.

    The old copy reads only the layer's own answers file, and the walk fills a
    key that file lacks, as a hand-run vanilla update of the layer leaves it,
    from the answers file of the layer that declares the question. A key
    neither file records has no answer to fill, so the old copy would render
    the question at its default. This runs before any layer does.

    Args:
        views: Each layer's scoped view at the recorded versions, keyed by layer
            name in walk order.
        recorded: The keys each layer's answers file records, keyed by layer
            name; a layer with no entry has no answers file.

    Raises:
        AnswersFileIncompleteError: If a required key is in neither a layer's
            own file nor its declaring layer's. The message names each such
            layer and its missing keys.
    """
    missing: dict[str, tuple[str, ...]] = {}
    for layer, view in views.items():
        own = recorded.get(layer, ())
        keys = tuple(
            key
            for key in required_answer_keys(view)
            if key not in own
            and key not in recorded.get(view.declared_by.get(key, layer), ())
        )
        if keys:
            missing[layer] = keys
    if missing:
        lines = "\n".join(
            f"  {layer}: {', '.join(keys)}" for layer, keys in missing.items()
        )
        raise AnswersFileIncompleteError(
            "Neither a layer's own answers file nor its declaring layer's "
            f"records answers its questions need:\n{lines}",
            missing=missing,
        )
