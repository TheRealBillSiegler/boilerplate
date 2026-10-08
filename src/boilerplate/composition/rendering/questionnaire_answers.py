"""The answers one questionnaire pass produced."""

from typing import Any, NamedTuple


class QuestionnaireAnswers(NamedTuple):
    """The answers one questionnaire pass produced.

    Attributes:
        user: Every question's answer, hidden (``when: false``) ones included.
        metadata: Copier's own ``_``-prefixed answers.
        hidden: Names of the questions that were never shown.
    """

    user: dict[str, Any]
    metadata: dict[str, Any]
    hidden: frozenset[str]
