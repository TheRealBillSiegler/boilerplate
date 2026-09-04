"""Common exceptions and utilities for the boilerplate package."""

from boilerplate.common.exceptions import (
    ActionRequiredError,
    BoilerplateError,
    DestinationNotEmptyError,
    DirectoryValidationError,
    InvalidTemplateSpecifierError,
    InvalidVersionError,
    MetadataValidationError,
    NonInteractiveRequiresForceError,
    TemplateNotFoundError,
)

__all__ = [
    "ActionRequiredError",
    "BoilerplateError",
    "DestinationNotEmptyError",
    "DirectoryValidationError",
    "InvalidTemplateSpecifierError",
    "InvalidVersionError",
    "MetadataValidationError",
    "NonInteractiveRequiresForceError",
    "TemplateNotFoundError",
]
