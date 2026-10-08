"""Find the git tag that names a template release."""

from packaging.version import InvalidVersion, Version

from boilerplate.common.exceptions import TemplateNotFoundError
from boilerplate.integrations.copier_types import get_git


def release_tag_for_version(source: str, version: Version) -> str:
    """Return the tag of `source` that names `version`.

    A paused update records each layer's target as a version, but Copier checks
    out a ref. The tag is found the way Copier finds its latest release: the
    source's tags that read as PEP 440 versions, so ``v1.2.0`` and ``1.2.0``
    both name 1.2.0.

    Args:
        source: The template source the answers file records in ``_src_path``.
        version: The release to find.

    Returns:
        The tag as the repository spells it.

    Raises:
        TemplateNotFoundError: If no tag of the source names `version`.
        plumbum.commands.processes.ProcessExecutionError: If the source cannot
            list its tags.
    """
    listing = get_git()("ls-remote", "--tags", "--refs", source)
    for line in listing.splitlines():
        tag = line.split("\t", 1)[1].removeprefix("refs/tags/")
        try:
            if Version(tag) == version:
                return tag
        except InvalidVersion:
            continue
    raise TemplateNotFoundError(
        f"No tag of '{source}' names version {version}.",
        remediation="Point the layer's _src_path at a source that has the release.",
    )
