"""Rendering models package.

Exposes execution models and internal helper types used by the rendering pipeline.
"""

from boilerplate.composition.rendering.models.execution_context import ExecutionContext
from boilerplate.composition.rendering.models.merged_template import MergedTemplate

__all__ = [
    "ExecutionContext",
    "MergedTemplate",
]
