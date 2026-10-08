"""Choose the versions a layer's old copy renders at."""
# Spec: docs/design/04-composition-engine.md §Safe Update

from collections.abc import Mapping

from boilerplate.composition.updating.versions.layer_versions import LayerVersions
from boilerplate.composition.updating.versions.old_copy import OldCopy

__all__ = ["old_copy_for"]


def old_copy_for(layer: LayerVersions, by_name: Mapping[str, LayerVersions]) -> OldCopy:
    """Return the versions `layer`'s old copy renders at.

    The old copy renders the layer's own template at the ``_commit`` its own
    answers file records and each ancestor at the version the lock records for
    it. The lock records the last complete update, so its versions match what
    the layer's files were last rendered against, which an ancestor's own
    ``_commit`` no longer does once the ancestor has updated ahead of its
    descendant.

    Args:
        layer: The layer whose step is about to run.
        by_name: Every layer of the project, keyed by name; it must hold each
            of `layer`'s ancestors.

    Returns:
        The layer's ref and the versions of the layer and its ancestors.

    Raises:
        ValueError: If the layer's ``_commit`` is missing or yields no version,
            so there is nothing to render its old copy at.

    Examples:
        >>> from boilerplate.types import SerializableVersion as V
        >>> core = LayerVersions(
        ...     name="core",
        ...     lock_version=V("1.0.0"),
        ...     commit="2.0.0",
        ...     commit_version=V("2.0.0"),
        ... )
        >>> service = LayerVersions(
        ...     name="service",
        ...     ancestors=("core",),
        ...     lock_version=V("1.0.0"),
        ...     commit="1.0.0",
        ...     commit_version=V("1.0.0"),
        ... )
        >>> old = old_copy_for(service, {"core": core, "service": service})
        >>> {name: str(version) for name, version in old.versions.items()}
        {'core': '1.0.0', 'service': '1.0.0'}
    """
    if layer.commit is None or layer.commit_version is None:
        raise ValueError(
            f"layer {layer.name!r} records no _commit that yields a version, "
            "so its old copy has no release to render at"
        )
    versions = {name: by_name[name].lock_version for name in layer.ancestors}
    versions[layer.name] = layer.commit_version
    return OldCopy(layer=layer.name, commit=layer.commit, versions=versions)
