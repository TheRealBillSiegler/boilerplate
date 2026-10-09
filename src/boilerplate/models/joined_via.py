"""How a layer joined a project."""
# Spec: docs/design/02-data-models.md §Lock File Model

from enum import StrEnum

__all__ = ["JoinedVia"]


class JoinedVia(StrEnum):
    """The way a layer entered the project the lock describes.

    ``EXTENDS`` covers the root template and every layer its ``extends`` closure
    reaches. ``ADD`` is a layer ``boilerplate add`` introduced, which the root's
    target version does not govern.
    """

    EXTENDS = "extends"
    ADD = "add"
