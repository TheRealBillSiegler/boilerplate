"""The ``boilerplate.lock`` file model."""
# Spec: docs/design/02-data-models.md §Lock File Model

import re
from collections.abc import Mapping
from typing import Final, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from boilerplate.models.lock_layer import LockLayer

__all__ = ["LOCK_SCHEMA_MAJOR", "LOCK_SCHEMA_VERSION", "BoilerplateLock"]

LOCK_SCHEMA_MAJOR: Final = 1
"""The lock schema major this tool reads and writes."""

LOCK_SCHEMA_VERSION: Final = f"boilerplate/lock@{LOCK_SCHEMA_MAJOR}"
"""The schema identifier this tool writes: ``namespace/schema@major``."""

_SUPPORTED_SCHEMA = re.compile(rf"^boilerplate/lock@{LOCK_SCHEMA_MAJOR}(\.\d+)*$")
_ANSWERS_HASH = re.compile(r"^[0-9a-f]{64}$")


class BoilerplateLock(BaseModel):
    """The lock Boilerplate writes into a project root after each operation.

    The lock records the last complete operation, so its layer versions match
    what each layer's files were last rendered against. Fields a later minor
    schema adds are ignored on read.

    Attributes:
        schema_version: The namespaced schema identifier; any minor of the
            supported major.
        boilerplate_version: The version of the tool that wrote the file.
        copier_version: The version of Copier used for rendering.
        created_at: When the project was created (UTC).
        updated_at: When the lock was last written (UTC).
        root_template: The specifier of the template that created the project.
        copier_answers_file_hashes: The SHA-256 hex digest of each layer's
            answers file, keyed by layer name; ``None`` when no layer has one.
        layers: One entry per template layer, in execution order; at least one,
            the root.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    schema_version: str = LOCK_SCHEMA_VERSION
    boilerplate_version: str
    copier_version: str
    created_at: AwareDatetime
    updated_at: AwareDatetime
    root_template: str
    copier_answers_file_hashes: Mapping[str, str] | None = None
    layers: tuple[LockLayer, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_invariants(self) -> Self:
        """Reject an unsupported schema, duplicate layers and stray hashes.

        Returns:
            The validated lock.

        Raises:
            ValueError: If the schema version is not of the supported major,
                two layers share a name, or a hash names a layer the lock does
                not list or is not a SHA-256 hex digest.
        """
        if not _SUPPORTED_SCHEMA.match(self.schema_version):
            raise ValueError(
                f"schema_version {self.schema_version!r} is not "
                f"{LOCK_SCHEMA_VERSION!r} or a minor of it"
            )
        names = [layer.name for layer in self.layers]
        duplicates = sorted({n for n in names if names.count(n) > 1})
        if duplicates:
            raise ValueError(f"layers repeat the name(s) {duplicates}")
        for layer, digest in (self.copier_answers_file_hashes or {}).items():
            if layer not in names:
                raise ValueError(f"answers file hash names unknown layer {layer!r}")
            if not _ANSWERS_HASH.match(digest):
                raise ValueError(f"answers file hash for {layer!r} is not SHA-256 hex")
        return self
