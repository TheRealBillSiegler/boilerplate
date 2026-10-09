"""Reading the lock a project had at one of its commits."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from boilerplate.common.exceptions import LockReadFailedError
from boilerplate.composition.staging.committed_lock import read_committed_lock
from boilerplate.models import BoilerplateLock, LockLayer
from boilerplate.project_state.lock_file import LOCK_FILE_NAME, write_lock
from boilerplate.types import SerializableVersion
from tests.boilerplate.templates.conftest import commit_all
from tests.integration.boilerplate.composition.staging.conftest import head

STAMP = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)
LOCK = BoilerplateLock(
    boilerplate_version="0.3.0",
    copier_version="9.18.1",
    created_at=STAMP,
    updated_at=STAMP,
    root_template="core@1.0.0",
    layers=(
        LockLayer(
            name="core",
            version=SerializableVersion("1.0.0"),
            source="https://example.com/core.git",
            commit="abc",
            checksum="sha256:" + "a" * 64,
        ),
    ),
)


class TestReadCommittedLock:
    def test_reads_the_lock_the_commit_holds(self, project: Path) -> None:
        """Read the committed lock, not the one the working tree holds since."""
        write_lock(project, LOCK)
        commit_all(project, "lock")
        commit = head(project)
        (project / LOCK_FILE_NAME).write_text("not: a lock\n", encoding="utf-8")

        assert read_committed_lock(project, commit) == LOCK

    def test_a_commit_without_a_lock_is_a_read_failure(self, project: Path) -> None:
        """Fail closed when the commit holds no lock."""
        with pytest.raises(LockReadFailedError):
            read_committed_lock(project, head(project))
