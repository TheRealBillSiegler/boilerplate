"""Read the answers a composed project's layers record in their answers files."""

from pathlib import Path
from typing import Any

from boilerplate.integrations.copier_types import load_answersfile_data
from boilerplate.project_state.answers_file import (
    ANSWERS_FILE_GLOB,
    answers_file_name,
    layer_of_answers_file,
)


def read_recorded_answers(project: Path, layer: str) -> dict[str, Any]:
    """Return the public answers `layer`'s answers file records in `project`.

    Args:
        project: The composed project.
        layer: The layer whose ``.copier-answers.<layer>.yml`` to read.

    Returns:
        The recorded answers without Copier's ``_``-prefixed keys; empty when
        the layer has no answers file.
    """
    recorded = load_answersfile_data(project, answers_file_name(layer)) or {}
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
        layer_of_answers_file(path.name)
        for path in sorted(project.glob(ANSWERS_FILE_GLOB))
    )
    return {layer: read_recorded_answers(project, layer) for layer in names}
