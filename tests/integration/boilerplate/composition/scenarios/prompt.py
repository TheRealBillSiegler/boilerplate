"""One question as Copier put it to a prompt, for the scenarios' prompt driver."""

from typing import NamedTuple


class Prompt(NamedTuple):
    """One question as Copier put it to the prompt.

    Attributes:
        name: The question's name.
        default: The default the prompt offered, as the value of its choice.
        shown: Whether the question was shown, rather than skipped by its
            ``when``.
    """

    name: str
    default: object
    shown: bool
