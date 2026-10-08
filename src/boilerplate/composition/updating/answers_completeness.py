"""Check that an answers file records every answer each layer's view asks for."""
# Spec: docs/design/04-composition-engine.md §Safe Update

from collections.abc import Mapping
from typing import Any

from boilerplate.common.exceptions import AnswersFileIncompleteError
from boilerplate.composition.rendering.hidden_questions import hidden_questions
from boilerplate.composition.updating.update_data import declaring_ancestors_answers
from boilerplate.composition.views import LayerView

__all__ = ["check_answers_complete", "required_answer_keys"]


def _is_secret(name: str, definition: Any, view: LayerView) -> bool:  # noqa: ANN401
    """Return whether Copier leaves question `name` out of the answers file."""
    if name in view.secret_questions:
        return True
    return isinstance(definition, Mapping) and bool(definition.get("secret"))  # pyright: ignore[reportUnknownMemberType]


def required_answer_keys(
    view: LayerView, answers: Mapping[str, Any]
) -> tuple[str, ...]:
    """Return the keys a layer's answers file must record for `view`.

    Copier records no answer for a secret question or for one its ``when``
    hides, so neither is required. A question is secret when it is marked
    ``secret: true`` or the view's ``_secret_questions`` names it; it is hidden
    when its ``when`` evaluates false under `answers` (``hidden_questions``),
    which leaves a ``when`` that reads a question `answers` lacks not hidden.

    Args:
        view: The layer's scoped view at the recorded versions.
        answers: The answers the ``when`` expressions render under.

    Returns:
        The question names that are neither secret nor hidden, in the view's
        question order. Directives (``_``-prefixed keys) are not questions.

    Examples:
        >>> view = LayerView(
        ...     {
        ...         "use_db": {"type": "bool"},
        ...         "token": {"secret": True, "default": ""},
        ...         "slug": {"when": False},
        ...         "db_url": {"when": "{{ use_db }}"},
        ...     },
        ...     (),
        ... )
        >>> required_answer_keys(view, {"use_db": False})
        ('use_db',)
        >>> required_answer_keys(view, {})
        ('use_db', 'db_url')
    """
    hidden = hidden_questions(view.questions, answers)
    return tuple(
        name
        for name, definition in view.questions.items()
        if not name.startswith("_")
        and name not in hidden
        and not _is_secret(name, definition, view)
    )


def check_answers_complete(
    views: Mapping[str, LayerView], recorded: Mapping[str, Mapping[str, Any]]
) -> None:
    """Stop the update when no answers file records a key a layer's view asks for.

    The old copy reads only the layer's own answers file, and the walk fills a
    key that file lacks, as a hand-run vanilla update of the layer leaves it,
    from the answers file of the layer that declares the question. A key
    neither file records has no answer to fill, so the old copy would render
    the question at its default. This runs before any layer does.

    Whether a question's ``when`` hides it is judged under the layer's own
    answers with, for each question an ancestor declares, the declaring
    ancestor's recorded answer on top: the data an update step passes.

    Args:
        views: Each layer's scoped view at the recorded versions, keyed by layer
            name in walk order.
        recorded: The answers each layer's answers file records, keyed by layer
            name; a layer with no entry has no answers file.

    Raises:
        AnswersFileIncompleteError: If a required key is in neither a layer's
            own file nor its declaring layer's. The message names each such
            layer and its missing keys.
    """
    missing: dict[str, tuple[str, ...]] = {}
    for layer, view in views.items():
        own = recorded.get(layer, {})
        answers = {
            **own,
            **declaring_ancestors_answers(
                layer=layer, declared_by=view.declared_by, recorded_by_layer=recorded
            ),
        }
        keys = tuple(
            key
            for key in required_answer_keys(view, answers)
            if key not in own
            and key not in recorded.get(view.declared_by.get(key, layer), {})
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
