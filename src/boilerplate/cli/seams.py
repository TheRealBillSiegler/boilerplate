"""Defines the injectable boundaries the CLI reaches through.

A test passes a ``Seams`` instance as ``obj`` to the Typer test runner
(``CliRunner.invoke(app, args, obj=seams)``); Click forwards it to
``Context.__init__``, and the app callback picks it up with
``ctx.ensure_object(Seams)`` before replacing ``ctx.obj`` with the
``CliContext`` subcommands see.
"""

from dataclasses import dataclass, field

from boilerplate.composition.rendering.engine import RenderEngine
from boilerplate.composition.rendering.renderer import Renderer


@dataclass(frozen=True)
class Seams:
    """Collaborators the CLI reaches through an injected boundary.

    A dataclass rather than a Pydantic model: ``Seams`` carries a
    collaborator with behavior, not data, and nothing on it is validated
    or serialized, so it gets none of the benefit a Pydantic model buys.

    Attributes:
        renderer: The renderer the ``new`` command drives; defaults to the
            real Copier-backed ``RenderEngine``.
    """

    renderer: Renderer = field(default_factory=RenderEngine)


__all__ = ["Seams"]
