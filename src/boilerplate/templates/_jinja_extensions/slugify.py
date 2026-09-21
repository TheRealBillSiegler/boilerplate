"""Jinja2 extension to expose the `slugify` filter via python-slugify.

Requires:
    python-slugify
"""

from jinja2.environment import Environment
from jinja2.ext import Extension
from slugify import slugify as _slugify


class SlugifyExtension(Extension):
    """Registers a `slugify` filter in a Jinja2 environment."""

    def __init__(self, environment: Environment) -> None:
        """Add the `slugify` filter to the given Jinja2 environment.

        Args:
            environment: Jinja2 environment to augment.
        """
        super().__init__(environment)
        environment.filters["slugify"] = _slugify
