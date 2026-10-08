"""Filter extension owned by a synthetic ``docs`` layer.

A layer that declares ``shout:ShoutExtension`` gets a ``shout`` filter, so a
file using it renders only under a view that carries the extension.
"""

from jinja2 import Environment
from jinja2.ext import Extension


def shout(value: object) -> str:
    """Upper-case `value` and append an exclamation mark.

    Args:
        value: The value to render.

    Returns:
        The shouted text.

    Examples:
        >>> shout("probe-app.docs.example")
        'PROBE-APP.DOCS.EXAMPLE!'
    """
    return f"{str(value).upper()}!"


class ShoutExtension(Extension):
    """Register the ``shout`` filter in a Jinja environment."""

    def __init__(self, environment: Environment) -> None:
        """Add the ``shout`` filter to `environment`.

        Args:
            environment: The Jinja environment to augment.
        """
        super().__init__(environment)
        environment.filters["shout"] = shout
