"""Read the answers a composed project's layers record in their answers files."""

from pathlib import Path
from typing import Any

from boilerplate.integrations.copier_types import load_answersfile_data

_ANSWERS_FILE_GLOB = ".copier-answers.*.yml"


def read_recorded_answers(project: Path, layer: str) -> dict[str, Any]:
    """Return the public answers `layer`'s answers file records in `project`.

    Args:
        project: The composed project.
        layer: The layer whose ``.copier-answers.<layer>.yml`` to read.

    Returns:
        The recorded answers without Copier's ``_``-prefixed keys; empty when
        the layer has no answers file.
    """
    recorded = load_answersfile_data(project, f".copier-answers.{layer}.yml") or {}
    return {k: v for k, v in recorded.items() if not str(k).startswith("_")}


def read_recorded_answers_by_layer(project: Path) -> dict[str, dict[str, Any]]:
    """Return every layer's public recorded answers, in answers-file name order.

    Args:
        project: The composed project.

    Returns:
        Each layer's recorded answers keyed by layer name, one entry per
        ``.copier-answers.<layer>.yml`` file in `project`.
    """
    names = (
        path.name.split(".")[2] for path in sorted(project.glob(_ANSWERS_FILE_GLOB))
    )
    return {layer: read_recorded_answers(project, layer) for layer in names}
