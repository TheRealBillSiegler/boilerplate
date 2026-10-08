"""The advisory lock a mutating operation holds on its project."""
# Spec: docs/design/07-operational-quality.md §Concurrency Control

import logging
import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from boilerplate.common.exceptions import ConcurrencyContentionError
from boilerplate.common.file_lock import FileLock
from boilerplate.composition.staging.git_commands import run_git

_logger = logging.getLogger(__name__)

LOCK_TIMEOUT_ENV = "BOILERPLATE_LOCK_TIMEOUT"
DEFAULT_LOCK_TIMEOUT = 60.0
_LOCK_FILE = "boilerplate-operation.lock"


def lock_timeout() -> float:
    """Read how long an operation waits for the project's lock.

    Returns:
        The seconds in ``BOILERPLATE_LOCK_TIMEOUT``, or the 60-second default
        when it is unset or is not a non-negative number.
    """
    raw = os.environ.get(LOCK_TIMEOUT_ENV)
    if raw is None:
        return DEFAULT_LOCK_TIMEOUT
    try:
        seconds = float(raw)
    except ValueError:
        seconds = -1.0
    if seconds < 0:
        _logger.warning(
            "Ignoring %s=%r: it must be a number of seconds, zero or more.",
            LOCK_TIMEOUT_ENV,
            raw,
        )
        return DEFAULT_LOCK_TIMEOUT
    return seconds


@contextmanager
def operation_lock(project: Path, *, timeout: float | None = None) -> Generator[None]:
    """Hold the exclusive lock of `project` while a mutating operation runs.

    The lock is a file in the repository's git directory rather than
    ``boilerplate.lock`` itself: that file is replaced by rename when the lock
    is written, which Windows refuses on a file the operation holds open, and a
    file in the working tree would make the project dirty.

    Args:
        project: The project, a git repository root.
        timeout: Seconds to wait for another operation to finish; the value of
            ``BOILERPLATE_LOCK_TIMEOUT`` (default 60) when omitted.

    Yields:
        Nothing; the lock is held for the duration of the block.

    Raises:
        ConcurrencyContentionError: If another operation still holds the lock
            when the timeout passes.
    """
    wait = lock_timeout() if timeout is None else timeout
    path = project / run_git(project, "rev-parse", "--git-path", _LOCK_FILE).strip()
    lock = FileLock(path)
    if not lock.acquire(wait):
        raise ConcurrencyContentionError(
            f"Another Boilerplate operation holds the lock on {project}; "
            f"waited {wait:g} seconds.",
            remediation="Wait for it to finish and run the command again, or "
            f"raise {LOCK_TIMEOUT_ENV}.",
        )
    try:
        yield
    finally:
        lock.release()
