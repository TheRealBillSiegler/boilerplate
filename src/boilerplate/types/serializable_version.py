"""SerializableVersion: a PEP 440-compliant, JSON-serializable version field.

This subclass of `packaging.version.Version` integrates with Pydantic v2 to support:
- Strict validation
- JSON-compatible serialization
- OpenAPI/JSON Schema generation
- Rich comparison and utility methods
"""
# Spec: docs/design/02-data-models.md §Version

from packaging.version import InvalidVersion
from packaging.version import Version as BaseVersion
from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema


class SerializableVersion(BaseVersion):
    """A validated, PEP 440-compliant, JSON-serializable version field.

    Inherits from `packaging.version.Version` and adds Pydantic integration.
    """

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source: type,
        _handler: GetCoreSchemaHandler,
    ) -> core_schema.CoreSchema:
        """Returns a Pydantic core schema supporting parsing and serialization.

        Args:
            _source: The source type for schema generation (ignored).
            _handler: A handler provided by Pydantic (ignored).

        Returns:
            The custom schema with validator and serializer.
        """
        return core_schema.with_info_plain_validator_function(
            cls._validate,
            serialization=core_schema.plain_serializer_function_ser_schema(
                str,
                return_schema=core_schema.str_schema(),
            ),
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        _core_schema: core_schema.CoreSchema,
        _handler: object,
    ) -> dict[str, object]:
        """Generates the JSON schema definition for OpenAPI or similar tools.

        Args:
            _core_schema: The core schema provided by Pydantic (ignored).
            _handler: The schema handler (ignored).

        Returns:
            The JSON schema representation.
        """
        return {
            "type": "string",
            "format": "version",
            "examples": ["1.0.0", "2.0.0b1", "0.0.1.post1"],
            "description": "PEP 440-compliant version string",
        }

    @classmethod
    def _validate(
        cls,
        value: object,
        _info: core_schema.ValidationInfo,
    ) -> "SerializableVersion":
        """Validates and converts input into a SerializableVersion instance.

        Args:
            value: The raw input value to validate.
            _info: Pydantic validation context (unused).

        Returns:
            A validated version instance.

        Raises:
            ValueError: If the input is not a valid PEP 440 version.
        """
        if isinstance(value, cls):
            return value
        if isinstance(value, BaseVersion):
            return cls(str(value))
        try:
            return cls(str(value))
        except InvalidVersion as exc:
            raise ValueError(f"Invalid version: {value}") from exc

    def __repr__(self) -> str:
        """Returns an eval-able representation of the version.

        Returns:
            A string of the form ``SerializableVersion('1.2.3')``.
        """
        return f"SerializableVersion({str(self)!r})"
