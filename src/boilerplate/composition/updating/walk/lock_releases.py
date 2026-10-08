"""The release each layer sits at, as the lock records it."""

from collections.abc import Mapping

from boilerplate.composition.updating.release_ref import ReleaseRef
from boilerplate.models import BoilerplateLock
from boilerplate.repository.release_tags import release_tag_for_version


def lock_releases(
    lock: BoilerplateLock, sources: Mapping[str, str]
) -> dict[str, ReleaseRef]:
    """Return each lock layer's release as a ref its source can check out.

    The lock records the commit a layer was rendered from; a layer whose lock
    entry records none is found by the tag that names its version.

    Args:
        lock: The project's lock.
        sources: The template source of each layer, keyed by layer name.

    Returns:
        The release of each layer, keyed by layer name in the lock's order.

    Raises:
        TemplateNotFoundError: If a layer without a recorded commit has no tag
            for its version.
    """
    return {
        entry.name: ReleaseRef(
            source=sources[entry.name],
            ref=entry.commit
            or release_tag_for_version(sources[entry.name], entry.version),
        )
        for entry in lock.layers
    }
