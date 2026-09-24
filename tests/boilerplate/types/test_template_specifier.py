"""Tests for TemplateSpecifier domain-specific exceptions.

Covers invalid name format, invalid specifier string parsing, and
invalid type conversion via the Pydantic-core validator.
"""

import pytest

from boilerplate.common.exceptions import InvalidTemplateSpecifierError
from boilerplate.types.template_specifier import TemplateSpecifier


def test_invalid_name_raises_invalid_template_specifier_error() -> None:
    with pytest.raises(InvalidTemplateSpecifierError, match="Invalid template name"):
        TemplateSpecifier("bad name with spaces", "1.0.0")


def test_invalid_specifier_string_raises_invalid_template_specifier_error() -> None:
    with pytest.raises(
        InvalidTemplateSpecifierError, match="Invalid template reference"
    ):
        TemplateSpecifier.from_string("missing_at_separator")


def test_invalid_type_conversion_raises_invalid_template_specifier_error() -> None:
    # Using the validator directly to simulate Pydantic conversion of wrong type
    with pytest.raises(InvalidTemplateSpecifierError, match="Cannot convert"):
        TemplateSpecifier._validate(123)  # type: ignore[arg-type]
