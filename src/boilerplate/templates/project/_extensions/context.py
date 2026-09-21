"""Context hook extension for injecting system Python version into template context.

This extension automatically injects python_version_major, python_version_minor,
and python_version_micro into the template context using the system's Python version.
This follows Copier's recommended approach for context enhancement.
"""

import sys
from typing import Any

from copier_template_extensions import ContextHook


class ContextUpdater(ContextHook):
    """Context hook that injects system Python version information."""

    def hook(self, context: dict[str, Any]) -> None:
        """Inject system Python version into the context.

        Args:
            context: The current template context dictionary (modified in place)
        """
        # Get system Python version info
        version_info = sys.version_info

        # Inject Python version information into context
        context["python_version_major"] = str(version_info.major)
        context["python_version_minor"] = str(version_info.minor)
        context["python_version_micro"] = str(version_info.micro)
