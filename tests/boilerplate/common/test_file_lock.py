"""The advisory file lock contends across handles and releases on demand."""

import threading
from pathlib import Path

from boilerplate.common.file_lock import FileLock


class TestFileLock:
    def test_second_lock_on_the_same_file_cannot_acquire(self, tmp_path: Path) -> None:
        first = FileLock(tmp_path / "a.lock")
        second = FileLock(tmp_path / "a.lock")
        assert first.try_acquire()

        assert not second.try_acquire()
        assert not second.held
        first.release()

    def test_lock_is_free_again_after_release(self, tmp_path: Path) -> None:
        first = FileLock(tmp_path / "a.lock")
        second = FileLock(tmp_path / "a.lock")
        first.try_acquire()
        first.release()

        assert second.try_acquire()
        second.release()

    def test_release_without_a_hold_does_nothing(self, tmp_path: Path) -> None:
        FileLock(tmp_path / "a.lock").release()

    def test_acquire_twice_on_one_object_is_idempotent(self, tmp_path: Path) -> None:
        lock = FileLock(tmp_path / "a.lock")

        assert lock.try_acquire()
        assert lock.try_acquire()
        lock.release()
        assert not lock.held

    def test_different_files_do_not_contend(self, tmp_path: Path) -> None:
        one, other = FileLock(tmp_path / "a.lock"), FileLock(tmp_path / "b.lock")

        assert one.try_acquire()
        assert other.try_acquire()
        one.release()
        other.release()

    def test_context_manager_releases_on_exit(self, tmp_path: Path) -> None:
        lock = FileLock(tmp_path / "a.lock")
        lock.try_acquire()

        with lock:
            assert lock.held

        assert not lock.held

    def test_acquire_gives_up_after_the_timeout(self, tmp_path: Path) -> None:
        holder = FileLock(tmp_path / "a.lock")
        holder.try_acquire()

        assert not FileLock(tmp_path / "a.lock").acquire(0.2, poll_interval=0.05)
        holder.release()

    def test_acquire_succeeds_once_the_holder_lets_go(self, tmp_path: Path) -> None:
        holder = FileLock(tmp_path / "a.lock")
        holder.try_acquire()
        timer = threading.Timer(0.2, holder.release)
        timer.start()

        waiter = FileLock(tmp_path / "a.lock")
        assert waiter.acquire(5, poll_interval=0.05)
        waiter.release()
        timer.join()
