"""Composition feature package.

Authoritative implementation for dependency resolution and composition.
"""

from boilerplate.composition.composer import Composer
from boilerplate.composition.resolution import Resolver

__all__ = [
    "Composer",
    "Resolver",
]
