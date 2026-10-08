"""Choose the release each layer of an update moves to."""

from collections.abc import Mapping

from boilerplate.common.exceptions import TemplateNotFoundError
from boilerplate.composition.updating.release_ref import ReleaseRef
from boilerplate.repository.release_checkouts import ReleaseCheckouts
from boilerplate.repository.release_tags import release_tag_for_version
from boilerplate.types.serializable_version import SerializableVersion

Releases = dict[str, ReleaseRef]
Versions = dict[str, SerializableVersion]


def named_releases(
    sources: Mapping[str, str],
    refs: Mapping[str, str | None],
    checkouts: ReleaseCheckouts,
) -> tuple[Releases, Versions]:
    """Return the release each layer of `refs` moves to, and its version.

    A layer whose ref is ``None`` moves to its latest release, as Copier
    resolves a template given no ref: the latest tag that reads as a version,
    prereleases left out.

    Args:
        sources: The template source of every layer, keyed by layer name.
        refs: The ref to check out for each layer to resolve, ``None`` for the
            latest release; only these layers are resolved.
        checkouts: The release checkouts of the update.

    Returns:
        The releases and the versions, each keyed by layer name in the order of
        `refs`. A release's ref is the tag Copier resolved for a ``None`` ref.

    Raises:
        TemplateNotFoundError: If a target reads as no version, as when a source
            has no release tag.
        plumbum.commands.processes.ProcessExecutionError: If a source cannot
            check its target out.
    """
    releases: Releases = {}
    versions: Versions = {}
    for layer, ref in refs.items():
        checkout = checkouts.get(sources[layer], ref)
        if checkout.version is None or checkout.commit is None:
            raise TemplateNotFoundError(
                f"Layer '{layer}': {ref or 'the latest release'} of "
                f"{sources[layer]} reads as no version.",
                remediation="Tag the template's releases, or name a tag with "
                "--target-version.",
            )
        releases[layer] = ReleaseRef(source=sources[layer], ref=ref or checkout.commit)
        versions[layer] = SerializableVersion(str(checkout.version))
    return releases, versions


def recorded_releases(
    sources: Mapping[str, str], targets: Mapping[str, SerializableVersion]
) -> Releases:
    """Return the release a paused update recorded as each layer's target.

    The record names versions, and a checkout needs a ref, so each version is
    resolved to the tag of its source that names it.

    Args:
        sources: The template source of every layer, keyed by layer name.
        targets: The recorded target version of each layer.

    Returns:
        The release of each layer, keyed by layer name in the order of `sources`.

    Raises:
        TemplateNotFoundError: If a source has no tag for a recorded target.
    """
    return {
        layer: ReleaseRef(
            source=source, ref=release_tag_for_version(source, targets[layer])
        )
        for layer, source in sources.items()
    }
