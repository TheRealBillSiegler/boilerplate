"""Read each layer's versions from the lock and the answers files."""
# Spec: docs/design/06-project-lifecycle.md §Step 1: Load Current State

from collections.abc import Mapping, Sequence
from pathlib import Path

from boilerplate.composition.updating.versions.layer_versions import LayerVersions
from boilerplate.integrations.copier_types import load_answersfile_data
from boilerplate.models import BoilerplateLock
from boilerplate.project_state.answers_file import answers_file_name
from boilerplate.repository.release_checkouts import ReleaseCheckouts
from boilerplate.types.serializable_version import SerializableVersion

__all__ = ["read_layer_versions"]


def _recorded_commit(project: Path, layer: str) -> tuple[str | None, str | None]:
    """Return the ``_commit`` and ``_src_path`` the layer's answers file records."""
    recorded = load_answersfile_data(project, answers_file_name(layer)) or {}
    commit = recorded.get("_commit")
    source = recorded.get("_src_path")
    return (
        str(commit) if commit is not None else None,
        str(source) if source is not None else None,
    )


def read_layer_versions(
    project: Path,
    lock: BoilerplateLock,
    ancestors: Mapping[str, Sequence[str]],
    checkouts: ReleaseCheckouts,
) -> tuple[LayerVersions, ...]:
    """Read what the lock and each answers file say about every layer's version.

    A ``_commit`` is read as a version the way Copier reads it, from its
    checkout in the layer's template repository, so the pure rules downstream
    take parsed versions only.

    Args:
        project: The project root holding the answers files.
        lock: The project's lock, which names the layers in walk order.
        ancestors: Each layer's ancestors, transitively, keyed by layer name; a
            layer not named has none.
        checkouts: The release checkouts of the update; each ``_commit`` is
            checked out through them, so a release the update reads again is
            cloned once.

    Returns:
        One entry per lock layer, in the lock's order. A layer with no answers
        file, no ``_commit``, no ``_src_path`` or a source that is not a git
        repository has no ``commit_version``.

    Raises:
        plumbum.commands.processes.ProcessExecutionError: If a layer's source
            cannot check its recorded commit out.
    """
    layers: list[LayerVersions] = []
    for entry in lock.layers:
        commit, source = _recorded_commit(project, entry.name)
        version = (
            checkouts.get(source, commit).version
            if commit is not None and source is not None
            else None
        )
        layers.append(
            LayerVersions(
                name=entry.name,
                ancestors=tuple(ancestors.get(entry.name, ())),
                lock_version=entry.version,
                commit=commit,
                commit_version=(
                    SerializableVersion(str(version)) if version is not None else None
                ),
            )
        )
    return tuple(layers)
