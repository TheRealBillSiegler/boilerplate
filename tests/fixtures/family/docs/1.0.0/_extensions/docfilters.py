"""Jinja filters the docs layer ships and other layers reuse."""

import re

from jinja2 import Environment
from jinja2.ext import Extension


def docs_anchor(value: object) -> str:
    """Convert `value` to the anchor a docs heading with that text gets.

    Args:
        value: The heading text.

    Returns:
        The text lower-cased with each run of other characters replaced by one
        hyphen.
    """
    return re.sub(r"[^0-9a-z]+", "-", str(value).lower()).strip("-")


class DocFilters(Extension):
    """Register the ``docs_anchor`` filter in a Jinja environment."""

    def __init__(self, environment: Environment) -> None:
        """Add the ``docs_anchor`` filter to `environment`.

        Args:
            environment: The Jinja environment to augment.
        """
        super().__init__(environment)
        environment.filters["docs_anchor"] = docs_anchor
