"""CLI context for shared runtime objects."""

from dataclasses import dataclass

from boilerplate.cli.display.core import Display
from boilerplate.composition.rendering.renderer import Renderer
from boilerplate.settings import Settings


@dataclass(frozen=True, kw_only=True)
class CliContext:
    """Simple context for CLI execution holding shared objects.

    A dataclass rather than a Pydantic model: ``CliContext`` bundles
    collaborators with behavior, not data, and nothing on it is validated
    or serialized, so it gets none of the benefit a Pydantic model buys.

    Attributes:
        settings: Loaded application settings.
        display: The user-facing output boundary.
        renderer: The renderer commands drive to produce a project;
            injected so tests can substitute a fake through ``Seams``.
        verbose: Whether debug logging is enabled.
        quiet: Whether informational output is suppressed.
        ci_mode: Whether ``--ci`` (or its env-var equivalent) was set.
    """

    settings: Settings
    display: Display
    renderer: Renderer
    verbose: bool = False
    quiet: bool = False
    ci_mode: bool = False
