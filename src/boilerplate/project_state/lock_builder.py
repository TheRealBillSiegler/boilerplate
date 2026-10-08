"""Build ``boilerplate.lock`` from a composed project's answers files."""
# Spec: docs/design/06-project-lifecycle.md §Step 4: Lock File Generation

import contextlib
import hashlib
from collections.abc import Sequence
from datetime import UTC, datetime
from importlib.metadata import version as installed_version
from pathlib import Path

from boilerplate.integrations.copier_types import load_answersfile_data
from boilerplate.models import BoilerplateLock, LockLayer
from boilerplate.repository.release_checkouts import ReleaseCheckouts
from boilerplate.repository.template_checksum import template_checksum
from boilerplate.types.serializable_version import SerializableVersion

__all__ = ["build_lock"]


def _answers_file_name(layer: str) -> str:
    """Return the name of `layer`'s answers file."""
    return f".copier-answers.{layer}.yml"


def _lock_layer(project: Path, layer: str, checkouts: ReleaseCheckouts) -> LockLayer:
    """Describe one layer from its answers file and the release it records.

    Raises:
        ValueError: If the answers file records no ``_src_path`` or ``_commit``,
            or the release reads as no version.
    """
    recorded = load_answersfile_data(project, _answers_file_name(layer)) or {}
    source, commit = recorded.get("_src_path"), recorded.get("_commit")
    if not source or not commit:
        raise ValueError(
            f"layer {layer!r}: {_answers_file_name(layer)} records no _src_path "
            "and _commit, so there is no release to lock"
        )
    release = checkouts.get(str(source), str(commit))
    if release.version is None:
        raise ValueError(
            f"layer {layer!r}: _commit {commit!r} of {source} reads as no version"
        )
    return LockLayer(
        name=layer,
        version=SerializableVersion(str(release.version)),
        source=str(source),
        commit=str(commit),
        checksum=template_checksum(release.path),
    )


def build_lock(
    project: Path,
    layers: Sequence[str],
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
    tag does not read as drifting from its own lock. Call it after the render or
    update the lock describes has finished.

    Args:
        project: The composed project holding the answers files.
        layers: The layers in composition order, ancestors first and the root
            last.
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
    """
    stamp = datetime.now(UTC)
    with contextlib.ExitStack() as stack:
        held = (
            stack.enter_context(ReleaseCheckouts()) if checkouts is None else checkouts
        )
        entries = tuple(_lock_layer(project, layer, held) for layer in layers)
    hashes = {
        layer: hashlib.sha256(
            (project / _answers_file_name(layer)).read_bytes()
        ).hexdigest()
        for layer in layers
    }
    root = entries[-1]
    return BoilerplateLock(
        boilerplate_version=boilerplate_version,
        copier_version=installed_version("copier"),
        created_at=previous.created_at if previous is not None else stamp,
        updated_at=stamp,
        root_template=f"{root.name}@{root.version}",
        copier_answers_file_hashes=hashes,
        layers=entries,
    )
