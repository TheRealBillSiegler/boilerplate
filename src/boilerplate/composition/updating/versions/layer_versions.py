"""The versions one layer of a project records, as the update checks read them."""
# Spec: docs/design/04-composition-engine.md §Safe Update

from pydantic import BaseModel, ConfigDict

from boilerplate.types.serializable_version import SerializableVersion

__all__ = ["LayerVersions"]


class LayerVersions(BaseModel):
    """What the lock and a layer's answers file say about the layer's version.

    The lock records the last complete update; the answers file's ``_commit``
    records what the layer itself was last updated to, which differs after a
    hand-run update or a paused walk. The model holds parsed values only, so the
    rules over it are pure; reading ``_commit`` as a version needs the layer's
    template repository and is the caller's job.

    Attributes:
        name: The layer's name, as in ``boilerplate.lock``.
        ancestors: Every ancestor of the layer, transitively, by name.
        lock_version: The version ``boilerplate.lock`` records for the layer.
        commit: The raw ``_commit`` the layer's answers file records, or
            ``None`` when it records none.
        commit_version: ``commit`` read as a version the way Copier reads it,
            or ``None`` when it yields none.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    ancestors: tuple[str, ...] = ()
    lock_version: SerializableVersion
    commit: str | None
    commit_version: SerializableVersion | None

    @property
    def disagrees_with_lock(self) -> bool:
        """Whether the layer's own recorded version differs from the lock's.

        A layer whose ``_commit`` yields no version is not counted: it cannot be
        compared, and the downgrade check stops on it.
        """
        return self.commit_version is not None and self.commit_version != (
            self.lock_version
        )
