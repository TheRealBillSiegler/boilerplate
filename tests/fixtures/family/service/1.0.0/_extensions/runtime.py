"""Context hook that gives the service layer its container user."""

from typing import Any

from copier_template_extensions import ContextHook


class RuntimeContext(ContextHook):
    """Inject ``container_user`` into the context of the service layer's render."""

    def hook(self, context: dict[str, Any]) -> None:
        """Add the user the container runs as.

        Args:
            context: The template context, modified in place.
        """
        context["container_user"] = "service"
