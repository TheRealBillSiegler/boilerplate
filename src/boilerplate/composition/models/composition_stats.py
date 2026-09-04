"""Typed, domain-centric composition statistics model.

Kept separate to follow one-class-per-file convention.
"""

from pydantic import BaseModel, ConfigDict


class CompositionStats(BaseModel):
    """Typed, domain-centric composition statistics.

    Attributes:
        layers_count: Number of layers in the composition.
        total_keys: Total mapping key count across the final configuration.
        total_scalars: Total scalar leaf count across the final configuration.
        top_level_fields: Number of top-level user fields (exclude directives).
        directives: Sorted directive keys present (leading underscore).
        tasks: Number of tasks declared under ``_tasks``.
        max_depth: Maximum nesting depth within the final configuration.
        delta_keys: Optional total keys touched across per-layer deltas (if present).
        delta_scalars: Optional total scalar leaves across per-layer deltas
            (if present).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    layers_count: int
    total_keys: int
    total_scalars: int
    top_level_fields: int
    directives: list[str]
    tasks: int
    max_depth: int
    delta_keys: int | None = None
    delta_scalars: int | None = None


__all__ = ["CompositionStats"]
