"""Hardened YAML loading shared by every Boilerplate YAML parse site.

Applies the parsing rules from docs/design/03-template-system.md (YAML Parsing
Rules) on top of plain ``yaml.safe_load`` semantics:

- Duplicate keys at the same mapping level raise an error instead of the last
  value silently winning.
- Total alias expansion is capped at ``MAX_ALIAS_NODES`` resolved nodes to
  guard against entity-expansion attacks ("billion laughs").

All failures raise ``yaml.YAMLError`` subclasses, so existing
``except yaml.YAMLError`` handling at call sites keeps working unchanged.
"""
# Spec: docs/design/03-template-system.md §YAML Parsing Rules

from collections.abc import Hashable
from typing import IO, Any, Final

import yaml
from yaml.composer import ComposerError
from yaml.constructor import ConstructorError
from yaml.error import Mark
from yaml.events import AliasEvent
from yaml.nodes import MappingNode, Node, SequenceNode

__all__ = [
    "MAX_ALIAS_NODES",
    "HardenedSafeLoader",
    "load_yaml",
]

MAX_ALIAS_NODES: Final[int] = 1000
"""Maximum total resolved alias nodes per document (design 03 recommends 1,000)."""


class HardenedSafeLoader(yaml.SafeLoader):
    """``yaml.SafeLoader`` that rejects duplicate keys and caps alias expansion.

    Each alias resolution is charged the full logical size of the subtree it
    references, so nested amplification (the classic billion-laughs shape)
    is caught even when the raw alias count is small.
    """

    def __init__(self, stream: str | IO[str]) -> None:
        """Initializes the loader with a full alias-expansion budget.

        Args:
            stream: YAML source text or a readable text stream.
        """
        super().__init__(stream)
        self._alias_budget = MAX_ALIAS_NODES

    def compose_node(self, parent: Node | None, index: int) -> Node | None:
        """Composes the next node, charging alias resolutions against the budget.

        Args:
            parent: The node under composition, if any.
            index: Position of this node within its parent.

        Returns:
            The composed node.

        Raises:
            yaml.composer.ComposerError: If total alias expansion exceeds
                ``MAX_ALIAS_NODES``.
        """
        is_alias = self.check_event(AliasEvent)
        mark = self.peek_event().start_mark if is_alias else None
        node = super().compose_node(parent, index)
        if is_alias and node is not None:
            self._charge_alias(node, mark)
        return node

    def construct_mapping(
        self, node: MappingNode, deep: bool = False
    ) -> dict[Hashable, Any]:
        """Constructs a mapping, rejecting duplicate keys.

        Args:
            node: The mapping node to construct.
            deep: Whether to construct nested objects eagerly.

        Returns:
            The constructed mapping.

        Raises:
            yaml.constructor.ConstructorError: If two keys at the same mapping
                level are equal.
        """
        if type(node) is not MappingNode:
            # Runtime guard: PyYAML's untyped internals can pass a non-mapping
            # node despite the annotation, and super() raises the canonical
            # error. `type() is` because isinstance here is flagged as
            # unnecessary under strict pyright (parameter is annotated).
            return super().construct_mapping(node, deep)
        self.flatten_mapping(node)
        seen: set[Hashable] = set()
        for key_node, _value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, Hashable):
                continue  # super() reports unhashable keys.
            if key in seen:
                raise ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    f"found duplicate key {key!r}; keys at the same mapping"
                    " level must be unique",
                    key_node.start_mark,
                )
            seen.add(key)
        return super().construct_mapping(node, deep)

    def _charge_alias(self, node: Node, mark: Mark | None) -> None:
        """Charges one alias resolution's logical subtree size to the budget.

        Walks the referenced subtree iteratively and aborts as soon as the
        budget is exhausted, so a hostile document costs at most
        ``MAX_ALIAS_NODES`` node visits per alias. Recursive aliases simply
        exhaust the budget and fail the same way.

        Args:
            node: The anchored node the alias resolved to.
            mark: Source location of the alias, for the error message.

        Raises:
            yaml.composer.ComposerError: If total alias expansion exceeds
                ``MAX_ALIAS_NODES``.
        """
        stack: list[Node] = [node]
        while stack:
            current = stack.pop()
            self._alias_budget -= 1
            if self._alias_budget < 0:
                raise ComposerError(
                    None,
                    None,
                    f"alias expansion exceeds the maximum of {MAX_ALIAS_NODES}"
                    " resolved nodes (possible entity-expansion attack);"
                    " reduce aliasing or inline the values",
                    mark,
                )
            if isinstance(current, SequenceNode):
                stack.extend(current.value)
            elif isinstance(current, MappingNode):
                for key_node, value_node in current.value:
                    stack.append(key_node)
                    stack.append(value_node)


# Any mirrors yaml.safe_load's return type; this is a drop-in replacement.
def load_yaml(stream: str | IO[str]) -> Any:  # noqa: ANN401
    """Parses a single YAML document with hardened ``safe_load`` semantics.

    Behaves like ``yaml.safe_load`` except that duplicate mapping keys are an
    error and total alias expansion is capped at ``MAX_ALIAS_NODES``.

    Args:
        stream: YAML source text or a readable text stream.

    Returns:
        The parsed document, or ``None`` for an empty document.

    Raises:
        yaml.YAMLError: If the document is malformed, contains duplicate
            mapping keys, or exceeds the alias-expansion cap.
    """
    # Safe: HardenedSafeLoader subclasses SafeLoader, so only the safe
    # constructor registry is available (no arbitrary object construction).
    return yaml.load(stream, HardenedSafeLoader)
