"""A platform-native advisory lock on a file."""

import sys
import time
from pathlib import Path
from types import TracebackType
from typing import IO, Self

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl


class FileLock:
    """An exclusive advisory lock on a file, held until released or the process exits.

    POSIX takes ``flock``; Windows locks the file's first byte with
    ``msvcrt.locking``, the byte-range lock behind ``LockFileEx``. The operating
    system releases the lock when the holding process exits, however it exits,
    so a crashed holder never leaves a lock behind. Two locks on the same path
    contend even inside one process, because each opens its own handle.

    Attributes:
        path: The file to lock; created if absent.
    """

    def __init__(self, path: Path) -> None:
        """Prepare a lock on `path`; nothing is opened until it is acquired.

        Args:
            path: The file to lock; its folder must exist.
        """
        self.path = path
        self._handle: IO[bytes] | None = None

    @property
    def held(self) -> bool:
        """Whether this lock currently holds the file."""
        return self._handle is not None

    def try_acquire(self) -> bool:
        """Take the lock if no one else holds it, without waiting.

        Returns:
            True when this lock now holds the file; False when another holder
            has it. Acquiring a lock this object already holds returns True.

        Raises:
            OSError: If the file cannot be opened.
        """
        if self._handle is not None:
            return True
        handle = self.path.open("a+b")
        try:
            _lock_first_byte(handle)
        except OSError:
            handle.close()
            return False
        self._handle = handle
        return True

    def acquire(self, timeout: float, poll_interval: float = 0.1) -> bool:
        """Take the lock, retrying until `timeout` seconds have passed.

        Args:
            timeout: How long to keep trying; zero tries once.
            poll_interval: Seconds to sleep between tries.

        Returns:
            True when this lock now holds the file; False when the timeout
            passed with another holder still on it.

        Raises:
            OSError: If the file cannot be opened.
        """
        deadline = time.monotonic() + timeout
        while not self.try_acquire():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            time.sleep(min(poll_interval, remaining))
        return True

    def release(self) -> None:
        """Release the lock; releasing a lock that is not held does nothing."""
        handle, self._handle = self._handle, None
        if handle is None:
            return
        try:
            _unlock_first_byte(handle)
        finally:
            handle.close()

    def __enter__(self) -> Self:
        """Return the lock, which the caller acquired already."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Release the lock."""
        self.release()


def _lock_first_byte(handle: IO[bytes]) -> None:
    """Take an exclusive, non-blocking lock on `handle`.

    Raises:
        OSError: If another holder has the lock.
    """
    if sys.platform == "win32":
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock_first_byte(handle: IO[bytes]) -> None:
    """Drop the lock `handle` holds."""
    if sys.platform == "win32":
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


__all__ = ["FileLock"]
