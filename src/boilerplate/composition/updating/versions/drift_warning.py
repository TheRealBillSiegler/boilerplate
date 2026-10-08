"""A layer that disagrees with the lock but does not stop the update."""
# Spec: docs/design/04-composition-engine.md §Safe Update

from pydantic import BaseModel, ConfigDict

from boilerplate.types.serializable_version import SerializableVersion

__all__ = ["DriftWarning"]


class DriftWarning(BaseModel):
    """One layer whose recorded version differs from the lock's.

    Attributes:
        layer: The disagreeing layer.
        commit: The ``_commit`` its answers file records.
        lock_version: The version ``boilerplate.lock`` records for it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    layer: str
    commit: str
    lock_version: SerializableVersion

    @property
    def message(self) -> str:
        """Describe the disagreement for a warning."""
        return (
            f"Layer '{self.layer}' records _commit {self.commit} but "
            f"boilerplate.lock records {self.lock_version}; the update "
            "proceeds from the layer's own _commit."
        )
