"""Defines the schema and validation logic for templates' `boilerplate.yml` files.

Each Copier template in the Boilerplate system includes a `boilerplate.yml` file
that declares its name, version, and any templates it extends. This model
ensures those files are valid and complete, and is used by the CLI and test
suite to read, validate, and inspect template metadata.
"""
# Spec: docs/design/02-data-models.md §TemplateMeta

from pathlib import Path
from typing import Final, Self

import yaml
from packaging.version import Version
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from boilerplate.common.yaml_loading import load_yaml
from boilerplate.types.serializable_version import SerializableVersion

__all__ = [
    "SCHEMA_VERSION",
    "TemplateMeta",
]

SCHEMA_VERSION: Final[SerializableVersion] = SerializableVersion("1.0")


class TemplateMeta(BaseModel):
    """Metadata for a single Copier template.

    Attributes:
        schema_version: The version of the `boilerplate.yml` schema.
        name: Logical name of the template (e.g., "project").
        description: Short human-readable description of the template.
        version: Semantic version of the template itself.
        extends: Names of parent templates this template builds upon.
    """

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )

    schema_version: SerializableVersion = SCHEMA_VERSION
    name: str = Field(..., min_length=1)
    description: str = Field(
        default="",
        description="Short human-readable description of the template.",
    )
    version: Version = Field(..., description="Semantic version of the template.")
    extends: list[str] = Field(default_factory=list)

    @field_serializer("version")
    def serialize_version(self, value: Version, _info: object) -> str:
        """Serializes the version as a string for YAML output.

        Args:
            value: The Version instance to serialize.
            _info: Additional context, not used here.

        Returns:
            The version as a string.
        """
        # Always serialize as SerializableVersion string
        return str(SerializableVersion(str(value)))

    @field_validator("schema_version", "version", mode="before")
    @classmethod
    def coerce_version(cls, value: object) -> SerializableVersion:
        """Coerces raw version-like input to a SerializableVersion.

        Args:
            value: The input value to convert.

        Returns:
            A validated SerializableVersion instance.

        Example:
            >>> TemplateMeta.coerce_version("1.2.3")
            SerializableVersion('1.2.3')
        """
        return SerializableVersion(str(value))

    @classmethod
    def load(cls, path: Path) -> Self:
        """Loads metadata from a boilerplate.yml file or directory containing one.

        Args:
            path: Path to either a boilerplate.yml file or a directory containing one.

        Returns:
            Parsed and validated metadata instance.

        Raises:
            FileNotFoundError: If boilerplate.yml does not exist.
            ValidationError: If required fields are missing or malformed.
        """
        meta_path = path / "boilerplate.yml" if path.is_dir() else path
        raw_data = load_yaml(meta_path.read_text(encoding="utf-8")) or {}
        return cls.model_validate(raw_data)

    def dump(self, path: Path, *, overwrite: bool = False) -> None:
        """Serializes the model to a YAML file.

        Args:
            path: Path to write the YAML file.
            overwrite: Whether to overwrite the file if it exists.
                Defaults to False.

        Raises:
            FileExistsError: If the file exists and overwrite is False.
        """
        if path.exists() and not overwrite:
            raise FileExistsError(path)

        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(
                self.model_dump(),
                f,
                sort_keys=False,
            )
