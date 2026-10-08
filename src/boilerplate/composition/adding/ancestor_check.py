"""Check that the project holds the ancestors of a layer being added.

The two preconditions are the last two of design 05 §add.
"""

from collections import deque
from collections.abc import Callable, Mapping, Sequence

from packaging.version import Version

from boilerplate.common.exceptions import (
    AddAncestorsMissingError,
    AddAncestorVersionError,
)
from boilerplate.types.template_specifier import TemplateSpecifier

__all__ = ["check_ancestors"]


def check_ancestors(
    layer: str,
    extends: Sequence[str],
    recorded: Mapping[str, Version],
    extends_of: Callable[[str], Sequence[str]],
) -> None:
    """Check that every ancestor of `layer` is in the project at an accepted version.

    An ancestor is a template the layer extends, directly or through another
    layer. A reference is ``name`` for any version or ``name@version`` for exactly
    that one. Missing ancestors are reported before a version mismatch, since
    adding them is the first remedy.

    Args:
        layer: The name of the layer being added.
        extends: The references the layer's ``boilerplate.yml`` extends.
        recorded: The version the lock records for each layer of the project.
        extends_of: Returns the references a layer of the project extends, as the
            project's copy of it declares them.

    Raises:
        AddAncestorsMissingError: If an ancestor is not in the project; the error
            names each missing layer.
        AddAncestorVersionError: If a layer's recorded version is not the one the
            layer's reference pins.
        InvalidTemplateSpecifierError: If a pinned reference is not a valid
            ``name@version`` string.
    """
    missing = _missing_ancestors(extends, recorded, extends_of)
    if missing:
        raise AddAncestorsMissingError(
            f"Cannot add '{layer}': it extends {', '.join(missing)}, which "
            "the project does not have.",
            layers=missing,
        )
    for reference in extends:
        if "@" not in reference:
            continue
        specifier = TemplateSpecifier.from_string(reference)
        name = specifier.name
        if specifier.version != recorded[name]:
            raise AddAncestorVersionError(
                f"Cannot add '{layer}': it extends '{reference}', but the "
                f"project records {name} {recorded[name]}.",
                ancestor=name,
                recorded=str(recorded[name]),
                constraint=reference,
            )


def _missing_ancestors(
    extends: Sequence[str],
    recorded: Mapping[str, Version],
    extends_of: Callable[[str], Sequence[str]],
) -> tuple[str, ...]:
    """Return the ancestors the references reach that the project lacks."""
    missing: dict[str, None] = {}
    seen: set[str] = set()
    pending = deque(reference.partition("@")[0] for reference in extends)
    while pending:
        name = pending.popleft()
        if name in seen:
            continue
        seen.add(name)
        if name in recorded:
            pending.extend(ref.partition("@")[0] for ref in extends_of(name))
        else:
            missing[name] = None
    return tuple(missing)
