"""The Click objects the CLI needs that Typer does not export.

Typer 0.26 vendored Click as a private package and declared direct Click use
unsupported, so the CLI never imports the ``click`` package. Typer exports
``BadParameter`` and ``Exit``, and the CLI uses those. It does not export the
usage-error base class that ``cli.py`` re-codes on its way out, the context
lookup ``utils.py`` uses to reach the active ``Display`` from a decorated
command, or the engine ``Context`` that ``TyperGroup``'s overridable methods
are typed with (``typer.Context`` is its subclass, so it cannot stand in for
an override's parameter). They are named here, once, so a rename upstream
fails in one place and in ``tests/boilerplate/cli/test_engine.py``.
"""

from typer._click.core import Context  # pyright: ignore[reportPrivateUsage]
from typer._click.exceptions import UsageError  # pyright: ignore[reportPrivateUsage]
from typer._click.globals import (  # pyright: ignore[reportPrivateUsage]
    get_current_context,
)

__all__ = ["Context", "UsageError", "get_current_context"]
