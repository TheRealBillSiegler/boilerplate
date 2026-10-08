"""Write the lock a created project ends with."""
# Spec: docs/design/06-project-lifecycle.md §Step 4: Lock File Generation

from pathlib import Path

from boilerplate.composition.models.composition import Composition
from boilerplate.models import BoilerplateLock
from boilerplate.project_state.folder_layer import FolderLayer
from boilerplate.project_state.lock_builder import build_lock
from boilerplate.project_state.lock_file import write_lock


def write_creation_lock(
    project: Path, composition: Composition, *, boilerplate_version: str
) -> BoilerplateLock:
    """Write the lock of the project `composition` just rendered into `project`.

    A layer rendered from a plain template folder records no ``_commit``, so it
    is locked at the version its ``boilerplate.yml`` declares with a null commit;
    a layer rendered from a git repository is locked at the release its answers
    file records. Call it only once every layer has rendered: the lock records
    the last complete operation.

    Args:
        project: The rendered project, holding each layer's answers file.
        composition: The composition that was rendered.
        boilerplate_version: The version of the tool writing the lock.

    Returns:
        The lock that was written.

    Raises:
        ValueError: If a layer's answers file records a release that reads as no
            version.
        OSError: If the lock cannot be written.
    """
    lock = build_lock(
        project,
        [
            FolderLayer(layer.name, layer.version, layer.path)
            for layer in composition.layers
        ],
        boilerplate_version=boilerplate_version,
    )
    write_lock(project, lock)
    return lock
