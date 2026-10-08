"""Tell which questions of a view their ``when`` hides under a set of answers."""
# Spec: docs/design/04-composition-engine.md §Safe Update

from collections.abc import Mapping
from typing import Any

from copier.errors import UserMessageError
from jinja2 import meta
from jinja2.exceptions import TemplateError

from boilerplate.integrations.copier_types import (
    MISSING,
    AnswersMap,
    Question,
    SandboxedEnvironment,
)

__all__ = ["RENDER_ERRORS", "hidden_questions"]

# What rendering a part of a question can raise: Copier wraps an undefined
# variable in ``UserMessageError`` but lets a compile error, such as an unknown
# filter, escape as Jinja's own ``TemplateError``.
RENDER_ERRORS = (UserMessageError, TemplateError)

# The filters Copier's own environment loads for every template
# (``Worker.jinja_env``), so a ``when`` such as ``{{ flag | bool }}`` renders.
_COPIER_DEFAULT_EXTENSIONS = ("jinja2_ansible_filters.AnsibleCoreFiltersExtension",)


def hidden_questions(
    questions: Mapping[str, Any],
    answers: Mapping[str, Any],
    *,
    jinja_env: SandboxedEnvironment | None = None,
) -> frozenset[str]:
    """Return the questions whose ``when`` evaluates false under `answers`.

    Walk the questions in order, as Copier asks them. A hidden question loses
    any answer `answers` holds for it and takes its rendered default instead,
    as in Copier, so a later ``when`` that reads it sees that default. A
    ``when`` that reads a question with no answer so far leaves its question
    not hidden: rendered leniently, the missing key would read as false and
    hide a question the answers do not settle. A ``when`` that cannot render
    leaves its question not hidden too, and Copier reports the template error
    itself when it asks.

    Args:
        questions: The view's questions in Copier's order, keyed by name;
            directives (``_``-prefixed keys) are skipped.
        answers: The answers the ``when`` expressions render under.
        jinja_env: The environment to render with; by default a sandboxed one
            with the filters Copier loads for every template. Filters a
            template's own extensions add render only under the caller's.

    Returns:
        The names of the hidden questions.

    Examples:
        >>> sorted(
        ...     hidden_questions(
        ...         {
        ...             "use_db": {"type": "bool"},
        ...             "db_url": {"when": "{{ use_db }}"},
        ...             "slug": {"when": False},
        ...         },
        ...         {"use_db": False},
        ...     )
        ... )
        ['db_url', 'slug']
    """
    env = jinja_env or SandboxedEnvironment(extensions=_COPIER_DEFAULT_EXTENSIONS)
    names = {name for name in questions if not name.startswith("_")}
    known = dict(answers)
    hidden: set[str] = set()
    for name, raw in questions.items():
        if name not in names:
            continue
        details = dict(raw) if isinstance(raw, Mapping) else {"default": raw}  # pyright: ignore[reportUnknownArgumentType]
        try:
            question = _question(name, details, known, env)
        except ValueError:
            # A definition Copier's Question refuses, such as a secret with no
            # default, is a template error Copier reports itself.
            continue
        if _is_asked(question, names - known.keys()):
            continue
        hidden.add(name)
        known.pop(name, None)
        default = _default(_question(name, details, known, env))
        if default is not MISSING:
            known[name] = default
    return frozenset(hidden)


def _question(
    name: str,
    details: Mapping[str, Any],
    known: Mapping[str, Any],
    env: SandboxedEnvironment,
) -> Question:
    """Build Copier's question for `name` against the answers known so far."""
    return Question(
        answers=AnswersMap(last=dict(known)),
        context=dict(known),
        jinja_env=env,
        var_name=name,
        **details,
    )


def _is_asked(question: Question, unanswered: set[str]) -> bool:
    """Return whether the question's ``when`` holds, or cannot be judged false."""
    when = question.when
    if isinstance(when, str):
        try:
            read = meta.find_undeclared_variables(question.jinja_env.parse(when))
        except TemplateError:
            return True
        if read & unanswered:
            return True
    try:
        return question.get_when()
    except RENDER_ERRORS:
        return True


def _default(question: Question) -> Any:  # noqa: ANN401
    """Return the question's rendered default, or ``MISSING`` when it has none."""
    try:
        return question.get_default()
    except RENDER_ERRORS:
        return MISSING
