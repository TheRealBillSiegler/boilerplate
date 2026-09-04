"""CLI context for shared runtime objects."""

from boilerplate.cli.display.core import Display
from boilerplate.settings import Settings


class CliContext:
    """Simple context for CLI execution holding shared objects."""

    def __init__(
        self,
        settings: Settings,
        display: Display,
        verbose: bool = False,
        quiet: bool = False,
        ci_mode: bool = False,
    ) -> None:
        """Initializes CLI context with settings, display, and flags."""
        self.settings = settings
        self.display = display
        self.verbose = verbose
        self.quiet = quiet
        self.ci_mode = ci_mode
