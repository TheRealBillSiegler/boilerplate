"""Build ``boilerplate.lock`` from a composed project's answers files."""
# Spec: docs/design/06-project-lifecycle.md §Step 4: Lock File Generation

import contextlib
import hashlib
from collections.abc import Sequence
from datetime import UTC, datetime
from importlib.metadata import version as installed_version
from pathlib import Path

from boilerplate.integrations.copier_types import load_answersfile_data
from boilerplate.models import BoilerplateLock, JoinedVia, LockLayer
from boilerplate.project_state.folder_layer import FolderLayer
from boilerplate.repository.release_checkouts import ReleaseCheckouts
from boilerplate.repository.template_checksum import template_checksum
from boilerplate.types.serializable_version import SerializableVersion

__all__ = ["build_lock", "mark_added"]


def _answers_file_name(layer: str) -> str:
    """Return the name of `layer`'s answers file."""
    return f".copier-answers.{layer}.yml"


def _layer_name(layer: str | FolderLayer) -> str:
    """Return the name of `layer`, given by name or as a `FolderLayer`."""
    return layer.name if isinstance(layer, FolderLayer) else layer


def _lock_layer(
    project: Path,
    layer: str | FolderLayer,
    checkouts: ReleaseCheckouts,
    joined_via: JoinedVia,
) -> LockLayer:
    """Describe one layer from its answers file and the release it records.

    A `FolderLayer` whose answers file records no ``_commit`` is described by
    its folder: its version, no commit, and the checksum of the folder.

    Raises:
        ValueError: If the answers file records no ``_src_path`` or ``_commit``
            and the layer is no `FolderLayer`, or the release reads as no
            version.
    """
    folder = layer if isinstance(layer, FolderLayer) else None
    name = _layer_name(layer)
    recorded = load_answersfile_data(project, _answers_file_name(name)) or {}
    source, commit = recorded.get("_src_path"), recorded.get("_commit")
    if not commit and folder is not None:
        return LockLayer(
            name=name,
            version=SerializableVersion(folder.version),
            source=str(source or folder.path),
            commit=None,
            checksum=template_checksum(folder.path),
        )
    if not source or not commit:
        raise ValueError(
            f"layer {name!r}: {_answers_file_name(name)} records no _src_path "
            "and _commit, so there is no release to lock"
        )
    release = checkouts.get(str(source), str(commit))
    if release.version is None:
        raise ValueError(
            f"layer {name!r}: _commit {commit!r} of {source} reads as no version"
        )
    return LockLayer(
        name=name,
        version=SerializableVersion(str(release.version)),
        joined_via=joined_via,
        source=str(source),
        commit=str(commit),
        checksum=template_checksum(release.path),
    )


def _origins(
    layers: Sequence[str | FolderLayer], previous: BoilerplateLock | None
) -> dict[str, JoinedVia]:
    """Return how each of `layers` joined: as `previous` says, else ``extends``."""
    recorded = (
        {entry.name: entry.joined_via for entry in previous.layers} if previous else {}
    )
    names = [_layer_name(layer) for layer in layers]
    return {name: recorded.get(name, JoinedVia.EXTENDS) for name in names}


def _root(entries: Sequence[LockLayer]) -> LockLayer:
    """Return the last entry that joined through ``extends``.

    Raises:
        ValueError: If no entry did.
    """
    for entry in reversed(entries):
        if entry.joined_via is JoinedVia.EXTENDS:
            return entry
    raise ValueError(
        "no layer joined through extends, so the lock has no root template"
    )


def build_lock(
    project: Path,
    layers: Sequence[str | FolderLayer],
    *,
    boilerplate_version: str,
    previous: BoilerplateLock | None = None,
    checkouts: ReleaseCheckouts | None = None,
) -> BoilerplateLock:
    """Build the lock of `project` as its answers files record it.

    Each layer's entry comes from its answers file: the source it records in
    ``_src_path`` and the release it records in ``_commit``, checked out with
    Copier's own clone for the version Copier reads from it and the checksum of
    the template content. The lock's version is therefore the one an update
    compares with each layer's ``_commit``, so a layer whose ``_commit`` is past a
    tag does not read as drifting from its own lock. Each entry records how its
    layer joined the project: as the previous lock records it, else ``extends``
    (``mark_added`` records a layer as added). The root template is the last layer
    that joined through ``extends``, so a layer added later never becomes the
    root. Call it after the render or update the lock describes has finished.

    Args:
        project: The composed project holding the answers files.
        layers: The layers in composition order, ancestors first and the root
            last. A layer that rendered from a plain template folder is given as
            a `FolderLayer`; when its answers file records no ``_commit`` it is
            locked at the folder's version with no commit. Any other layer must
            record a release.
        boilerplate_version: The version of the tool writing the lock.
        previous: The lock being replaced, if any; the new lock keeps its
            creation time.
        checkouts: Release checkouts the caller already holds, which the lock
            reads and leaves in place; by default the releases are cloned for
            the call and removed.

    Returns:
        The lock, not yet written.

    Raises:
        ValueError: If a layer's answers file records no release that reads as a
            version.
        plumbum.commands.processes.ProcessExecutionError: If a layer's source
            cannot check its recorded release out.
        ValueError: If no layer joined through ``extends``, which leaves the
            lock without a root template.
    """
    origins = _origins(layers, previous)
    stamp = datetime.now(UTC)
    with contextlib.ExitStack() as stack:
        held = (
            stack.enter_context(ReleaseCheckouts()) if checkouts is None else checkouts
        )
        entries = tuple(
            _lock_layer(project, layer, held, origins[_layer_name(layer)])
            for layer in layers
        )
    hashes = {
        entry.name: hashlib.sha256(
            (project / _answers_file_name(entry.name)).read_bytes()
        ).hexdigest()
        for entry in entries
        if (project / _answers_file_name(entry.name)).is_file()
    }
    root = _root(entries)
    return BoilerplateLock(
        boilerplate_version=boilerplate_version,
        copier_version=installed_version("copier"),
        created_at=previous.created_at if previous is not None else stamp,
        updated_at=stamp,
        root_template=f"{root.name}@{root.version}",
        copier_answers_file_hashes=hashes,
        layers=entries,
    )


def mark_added(lock: BoilerplateLock, layer: str) -> BoilerplateLock:
    """Return `lock` with `layer` recorded as introduced by ``boilerplate add``.

    The root template is recomputed, though marking a layer as added never moves
    it off the layers that joined through ``extends``.

    Args:
        lock: The lock that lists `layer`.
        layer: The name of the layer to record as added.

    Returns:
        The lock with that entry's origin set to ``add``.

    Raises:
        ValueError: If the lock lists no such layer, or no layer is left that
            joined through ``extends``.
    """
    if layer not in {entry.name for entry in lock.layers}:
        raise ValueError(f"the lock lists no layer {layer!r}")
    entries = tuple(
        entry.model_copy(update={"joined_via": JoinedVia.ADD})
        if entry.name == layer
        else entry
        for entry in lock.layers
    )
    root = _root(entries)
    return lock.model_copy(
        update={"layers": entries, "root_template": f"{root.name}@{root.version}"}
    )
