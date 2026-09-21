"""Defines the renderer contract callers drive.

``RenderEngine`` is the Copier-backed implementation.
"""

from typing import Protocol

from boilerplate.composition.models.composition import Composition
from boilerplate.composition.rendering.models.execution_context import ExecutionContext
from boilerplate.models.template_info import TemplateInfo


class Renderer(Protocol):
    """Structural contract for rendering a composition into a destination.

    ``RenderEngine`` satisfies this shape without inheriting from it —
    callers depend on the Protocol so a test can substitute any object
    with a matching ``render`` method, real or fake.
    """

    def render(self, composition: Composition, ctx: ExecutionContext) -> TemplateInfo:
        """Render all layers of ``composition`` into ``ctx.destination``.

        Args:
            composition: Computed composition (layers and final merged schema).
            ctx: Execution parameters including destination path and base context.

        Returns:
            Information about the final (root) template after render.
        """
        ...


__all__ = ["Renderer"]
