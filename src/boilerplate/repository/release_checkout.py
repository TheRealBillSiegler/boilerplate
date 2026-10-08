"""Check a template out at a release with Copier's own clone."""

from collections.abc import Generator
from contextlib import contextmanager

from boilerplate.integrations.copier_types import Template
from boilerplate.repository.checked_out_release import CheckedOutRelease


@contextmanager
def checked_out_release(source: str, ref: str | None) -> Generator[CheckedOutRelease]:
    """Check `source` out at `ref` for the duration of a block.

    Copier clones a git-backed source into a temporary directory and checks the
    ref out; a ``git describe`` string such as ``1.1.0-1-gabc1234``, the form
    Copier records in ``_commit``, is a ref git resolves. With no ref Copier
    resolves the latest release tag, ignoring prereleases. The clone is removed
    when the block ends, also when it raises.

    Args:
        source: The template source the answers file records in ``_src_path``.
        ref: The tag, ``git describe`` string or commit to check out; ``None``
            for the latest release tag.

    Yields:
        The checkout, valid inside the block only.

    Raises:
        plumbum.commands.processes.ProcessExecutionError: If the source cannot
            check the ref out.
    """
    template = Template(url=source, ref=ref)
    try:
        yield CheckedOutRelease(
            path=template.local_abspath,
            commit=template.commit,
            version=template.version,
        )
    finally:
        template._cleanup()  # pyright: ignore[reportPrivateUsage]
