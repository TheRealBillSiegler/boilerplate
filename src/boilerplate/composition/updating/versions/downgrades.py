"""Reject an update that moves a layer to an older version."""
# Spec: docs/design/06-project-lifecycle.md §Step 2: Resolve Target

from collections.abc import Mapping, Sequence

from boilerplate.common.exceptions import UpdateDowngradeError
from boilerplate.composition.updating.versions.layer_versions import LayerVersions
from boilerplate.types.serializable_version import SerializableVersion

__all__ = ["reject_downgrades"]


def reject_downgrades(
    layers: Sequence[LayerVersions], targets: Mapping[str, SerializableVersion]
) -> None:
    """Stop before any layer runs when a target is older than the layer's version.

    Each target is compared with the version the layer's own answers file
    records in ``_commit``, read the way Copier reads it, so a commit past a
    tag counts as newer than the tag. There is no override: the way back from an
    applied update is reverting the commit that recorded it.

    Args:
        layers: The layers the update is about to run.
        targets: The version each of those layers moves to, keyed by name.

    Raises:
        UpdateDowngradeError: If a target is older than the layer's recorded
            version, or the layer's ``_commit`` yields no version to compare.
            The error names the layer, its recorded version and the target.
        ValueError: If a layer has no target.
    """
    for layer in layers:
        if layer.name not in targets:
            raise ValueError(f"layer {layer.name!r} has no target version")
        target = targets[layer.name]
        recorded = layer.commit_version
        if recorded is None:
            raise UpdateDowngradeError(
                f"Layer '{layer.name}' records _commit {layer.commit!r}, which "
                f"yields no version to compare with the target {target}.",
                layer=layer.name,
                target=str(target),
            )
        if target < recorded:
            raise UpdateDowngradeError(
                f"Layer '{layer.name}' is at {recorded}; the target {target} is "
                "older. An update never moves a layer back.",
                layer=layer.name,
                recorded=str(recorded),
                target=str(target),
            )
