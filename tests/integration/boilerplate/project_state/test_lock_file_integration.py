"""The lock file through the real filesystem: round trip and fail-closed refusal."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from boilerplate.common.exceptions import LockSchemaUnsupportedError
from boilerplate.models import BoilerplateLock, LockLayer
from boilerplate.project_state.lock_file import LOCK_FILE_NAME, read_lock, write_lock
from boilerplate.types import SerializableVersion

CREATED = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)


def _lock(updated_at: datetime, app_version: str) -> BoilerplateLock:
    return BoilerplateLock(
        boilerplate_version="0.3.0",
        copier_version="9.18.1",
        created_at=CREATED,
        updated_at=updated_at,
        root_template=f"app@{app_version}",
        layers=(
            LockLayer(
                name="app",
                version=SerializableVersion(app_version),
                source="https://example.com/app.git",
                commit="abc",
                checksum="sha256:" + "a" * 64,
            ),
        ),
    )


class TestLockRoundTrip:
    """A lock written twice reads back as the second write."""

    def test_a_second_write_replaces_the_first(self, tmp_path: Path) -> None:
        write_lock(tmp_path, _lock(CREATED, "1.0.0"))
        later = _lock(CREATED + timedelta(days=1), "1.1.0")

        write_lock(tmp_path, later)

        assert read_lock(tmp_path) == later
        assert [p.name for p in tmp_path.iterdir()] == [LOCK_FILE_NAME]


class TestUnknownSchemaRefusal:
    """A lock from a newer generation is refused and never rewritten."""

    def test_the_refused_file_is_left_byte_identical(self, tmp_path: Path) -> None:
        path = tmp_path / LOCK_FILE_NAME
        newer = b"schema_version: boilerplate/lock@2\nlayers: {changed: shape}\n"
        path.write_bytes(newer)

        with pytest.raises(LockSchemaUnsupportedError):
            read_lock(tmp_path)

        assert path.read_bytes() == newer
