"""TemplateSpecifier: a Pydantic model for template name@version specifiers.

This class provides type-safe handling of template specifiers with validation,
serialization, and rich comparison methods. It replaces string-based
specifier handling with a proper first-class citizen.
"""
# Spec: docs/design/02-data-models.md §TemplateSpecifier

import re
from typing import Self

from packaging.version import InvalidVersion, Version
from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema

from boilerplate.common.exceptions import InvalidTemplateSpecifierError


class TemplateSpecifier:
    """A validated template specifier consisting of name and version.

    Represents a template identifier in the format "name@version" with
    proper validation and type safety.

    Attributes:
        name: The template name (alphanumeric, underscore, hyphen only).
        version: The semantic version of the template.

    Examples:
        >>> specifier = TemplateSpecifier("streamlit", "2.0.0")
        >>> str(specifier)
        'streamlit@2.0.0'
        >>> specifier.name
        'streamlit'
        >>> str(specifier.version)
        '2.0.0'

        >>> # Parse from string
        >>> spec2 = TemplateSpecifier.from_string("fastapi@1.0.0-beta")
        >>> spec2.name
        'fastapi'
        >>> str(spec2.version)
        '1.0.0b0'

        >>> # Comparison
        >>> spec1 = TemplateSpecifier("app", "1.0.0")
        >>> spec2 = TemplateSpecifier("app", "2.0.0")
        >>> spec1 < spec2
        True
        >>> spec1 == TemplateSpecifier("app", "1.0.0")
        True
    """

    name: str
    version: Version

    # Pattern for valid template names
    NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+$")
    # Pattern for parsing specifier strings
    SPECIFIER_PATTERN = re.compile(r"^(?P<name>[a-zA-Z0-9_\-]+)@(?P<version>.+)$")

    def __init__(self, name: str, version: str | Version) -> None:
        """Initialize a template specifier.

        Args:
            name: The template name.
            version: The template version.

        Raises:
            InvalidTemplateSpecifierError: If name or version format is invalid.
        """
        if not self.NAME_PATTERN.match(name):
            raise InvalidTemplateSpecifierError(f"Invalid template name format: {name}")

        self.name = name
        try:
            self.version = Version(version) if isinstance(version, str) else version
        except InvalidVersion as e:
            raise InvalidTemplateSpecifierError(
                f"Invalid version format: {version}"
            ) from e

    @classmethod
    def from_string(cls, specifier_string: str) -> Self:
        """Parse a template specifier from a string.

        Args:
            specifier_string: Specifier string in format "name@version".

        Returns:
            The parsed template specifier.

        Raises:
            InvalidTemplateSpecifierError: If the specifier string format is invalid.
            InvalidVersion: If the version format is invalid.

        Examples:
            >>> specifier = TemplateSpecifier.from_string("project@1.2.3")
            >>> specifier.name
            'project'
            >>> str(specifier.version)
            '1.2.3'
        """
        match = cls.SPECIFIER_PATTERN.match(specifier_string)
        if not match:
            raise InvalidTemplateSpecifierError(
                f"Invalid specifier format: {specifier_string}"
            )

        return cls(match.group("name"), match.group("version"))

    def __str__(self) -> str:
        """Return the string representation in format 'name@version'."""
        return f"{self.name}@{self.version}"

    def __repr__(self) -> str:
        """Return the detailed string representation."""
        return f"TemplateSpecifier(name='{self.name}', version='{self.version}')"

    def __eq__(self, other: object) -> bool:
        """Check equality with another TemplateSpecifier."""
        if not isinstance(other, type(self)):
            return NotImplemented
        return self.name == other.name and self.version == other.version

    def __hash__(self) -> int:
        """Return a hash for use in sets and dictionaries."""
        return hash((self.name, self.version))

    def __lt__(self, other: Self) -> bool:
        """Compare with another TemplateSpecifier by name then version."""
        if not isinstance(other, type(self)):
            return NotImplemented
        if self.name != other.name:
            return self.name < other.name
        return self.version < other.version

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source: type,
        _handler: GetCoreSchemaHandler,
    ) -> core_schema.CoreSchema:
        """Return a Pydantic core schema for validation and serialization.

        Returns:
            The schema for Pydantic integration.
        """
        return core_schema.with_info_plain_validator_function(
            cls._validate,
            serialization=core_schema.plain_serializer_function_ser_schema(
                str,
                return_schema=core_schema.str_schema(),
            ),
        )

    @classmethod
    def _validate(cls, value: str | Self, _info: object = None) -> Self:
        """Validate and convert input to TemplateSpecifier.

        Args:
            value: Input value (string or TemplateSpecifier).
            _info: Validation info (unused).

        Returns:
            The validated template specifier.
        """
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            return cls.from_string(value)
        raise InvalidTemplateSpecifierError(
            f"Cannot convert {type(value)} to TemplateSpecifier"
        )


__all__ = [
    "TemplateSpecifier",
]
