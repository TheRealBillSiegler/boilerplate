"""Context hook that overwrites a variable the base layer's files render.

A layer that declares ``leak_hook:LeakHook`` sets ``description`` to
``LEAKED`` in every render its extensions reach, so a file shows which
layer's extensions it rendered under.
"""

from typing import Any

from copier_template_extensions import ContextHook

LEAKED = "LEAKED"


class LeakHook(ContextHook):
    """Overwrite ``description`` in every render context it is installed in."""

    def hook(self, context: dict[str, Any]) -> None:
        """Set ``description`` to the ``LEAKED`` sentinel.

        Args:
            context: The render context, modified in place.
        """
        context["description"] = LEAKED
