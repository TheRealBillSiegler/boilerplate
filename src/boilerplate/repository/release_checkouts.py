"""Hold the release checkouts one operation reads, each cloned once."""

from contextlib import ExitStack
from types import TracebackType
from typing import Self

from boilerplate.repository.checked_out_release import CheckedOutRelease
from boilerplate.repository.release_checkout import checked_out_release


class ReleaseCheckouts:
    """A set of release checkouts that live until its block ends.

    An update reads the same release of a layer for several views, and the views
    keep paths into the checkouts, so the checkouts outlive any one view. A
    checkout is cloned the first time it is asked for and handed back after
    that; leaving the block removes every clone, also when it raises.
    """

    def __init__(self) -> None:
        """Prepare an empty set; nothing is cloned until a checkout is asked for."""
        self._stack = ExitStack()
        self._releases: dict[tuple[str, str | None], CheckedOutRelease] = {}

    def get(self, source: str, ref: str | None) -> CheckedOutRelease:
        """Return the checkout of `source` at `ref`, cloning it on first use.

        A checkout with no ref is the latest release; it is also kept under the
        tag it resolved to, so asking for that tag later clones nothing.

        Args:
            source: The template source the answers file records in ``_src_path``.
            ref: The tag, ``git describe`` string or commit to check out;
                ``None`` for the latest release tag.

        Returns:
            The checkout, valid until the block ends.

        Raises:
            plumbum.commands.processes.ProcessExecutionError: If the source
                cannot check the ref out.
        """
        key = (source, ref)
        if key not in self._releases:
            release = self._stack.enter_context(checked_out_release(source, ref))
            self._releases[key] = release
            if ref is None and release.commit is not None:
                self._releases.setdefault((source, release.commit), release)
        return self._releases[key]

    def __enter__(self) -> Self:
        """Open the set.

        Returns:
            The set.
        """
        self._stack.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Remove every clone the block made."""
        self._stack.__exit__(exc_type, exc, traceback)
        self._releases.clear()
