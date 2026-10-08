"""Find where each layer of a project fetches its template from."""

from pathlib import Path

from boilerplate.integrations.copier_types import load_answersfile_data
from boilerplate.models import BoilerplateLock


def read_layer_sources(project: Path, lock: BoilerplateLock) -> dict[str, str]:
    """Return each lock layer's template source.

    The layer's answers file records the source Copier updates from in
    ``_src_path``; a layer whose file records none falls back to the source the
    lock records.

    Args:
        project: The project holding the answers files.
        lock: The project's lock, which names the layers.

    Returns:
        The source of each layer, keyed by layer name in the lock's order.
    """
    sources: dict[str, str] = {}
    for entry in lock.layers:
        recorded = load_answersfile_data(project, f".copier-answers.{entry.name}.yml")
        source = (recorded or {}).get("_src_path")
        sources[entry.name] = str(source) if source else entry.source
    return sources
