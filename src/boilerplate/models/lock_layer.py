"""One template layer's entry in ``boilerplate.lock``."""
# Spec: docs/design/02-data-models.md §Lock File Model

from pydantic import BaseModel, ConfigDict, Field

from boilerplate.types.serializable_version import SerializableVersion

__all__ = ["LockLayer"]

_CHECKSUM_PATTERN = r"^[a-z0-9]+:[0-9a-f]+$"


class LockLayer(BaseModel):
    """What the lock records about one template layer's last complete render.

    Fields a later minor schema adds are ignored on read, because Boilerplate
    parses any lock of the supported major.

    Attributes:
        name: The template name.
        version: The exact version rendered.
        source: The URI or filesystem path of the template.
        commit: The git commit hash of the template at render time, if any.
        checksum: The digest of the template source directory, prefixed with
            its algorithm (``sha256:<hex>``).
        subdirectory: Reserved for a shared-bundle source; ``None`` today.
        source_bundle: Reserved for a shared-bundle source; ``None`` today.
        trust_tier: The trust level of the layer's source at resolution time,
            when the source declares one. Never consulted.
        bundle_uri: Reserved for air-gap restoration; never consulted.
        bundle_checksum: Reserved for air-gap restoration; never consulted.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    name: str = Field(min_length=1)
    version: SerializableVersion
    source: str
    commit: str | None = None
    checksum: str = Field(pattern=_CHECKSUM_PATTERN)
    subdirectory: str | None = None
    source_bundle: str | None = None
    trust_tier: str | None = None
    bundle_uri: str | None = None
    bundle_checksum: str | None = None
