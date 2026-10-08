"""The versions a layer's old copy renders at."""
# Spec: docs/design/04-composition-engine.md §Safe Update

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict

from boilerplate.types.serializable_version import SerializableVersion

__all__ = ["OldCopy"]


class OldCopy(BaseModel):
    """The release a layer's step renders its old copy at, with its ancestors'.

    Attributes:
        layer: The layer the old copy is for.
        commit: The layer's own recorded ``_commit``, the ref its template is
            checked out at.
        versions: The version of the layer and of each ancestor the recorded
            scoped view is composed at: the layer at its own ``_commit``, each
            ancestor at the lock's version.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    layer: str
    commit: str
    versions: Mapping[str, SerializableVersion]
