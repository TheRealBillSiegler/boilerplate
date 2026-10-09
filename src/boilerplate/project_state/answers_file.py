"""Name a layer's answers file, and recover the layer from the name."""
# Spec: docs/design/04-composition-engine.md §Per-Layer Render Loop

from typing import Final

__all__ = ["ANSWERS_FILE_GLOB", "answers_file_name", "layer_of_answers_file"]

_PREFIX: Final = ".copier-answers."
_SUFFIX: Final = ".yml"

ANSWERS_FILE_GLOB: Final = f"{_PREFIX}*{_SUFFIX}"


def answers_file_name(layer: str) -> str:
    """Return the name of `layer`'s answers file.

    Args:
        layer: The layer's name.

    Returns:
        The file name Copier writes for the layer, ``.copier-answers.<layer>.yml``.

    Examples:
        >>> answers_file_name("core")
        '.copier-answers.core.yml'
    """
    return f"{_PREFIX}{layer}{_SUFFIX}"


def layer_of_answers_file(name: str) -> str:
    """Return the layer an answers file named `name` belongs to.

    Args:
        name: A file name matching ``ANSWERS_FILE_GLOB``.

    Returns:
        The layer's name, whole even when it contains dots.

    Examples:
        >>> layer_of_answers_file(".copier-answers.my.layer.yml")
        'my.layer'
    """
    return name.removeprefix(_PREFIX).removesuffix(_SUFFIX)
