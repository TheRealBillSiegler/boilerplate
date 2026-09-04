"""Template catalog for Boilerplate.

This package provides the TemplateCatalog domain concept - an in-memory
registry that indexes templates from multiple repositories and provides
unified lookup and resolution capabilities.
"""

from boilerplate.catalog.catalog import TemplateCatalog

__all__ = [
    "TemplateCatalog",
]
