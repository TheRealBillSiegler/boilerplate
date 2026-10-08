"""Builders shared by the version-resolution tests."""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

from boilerplate.composition.updating.versions import LayerVersions
from boilerplate.models import ChangeClassification, MigrationRecord, MigrationStatus
from boilerplate.types import SerializableVersion

STAMP = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)


def v(version: str) -> SerializableVersion:
    """Return `version` as a PEP 440 version."""
    return SerializableVersion(version)


def layer(
    name: str,
    lock: str,
    *,
    commit: str | None = None,
    ancestors: Sequence[str] = (),
) -> LayerVersions:
    """Build a layer whose answers file records `commit` (default: the lock's).

    The commit is read as its own version, as a bare tag is; use
    ``no_version_layer`` for a commit that yields no version.
    """
    recorded = lock if commit is None else commit
    return LayerVersions(
        name=name,
        ancestors=tuple(ancestors),
        lock_version=v(lock),
        commit=recorded,
        commit_version=v(recorded),
    )


def past_tag_layer(name: str, lock: str, described: str, version: str) -> LayerVersions:
    """Build a layer recorded past a tag: a ``git describe`` string and its version."""
    return LayerVersions(
        name=name,
        lock_version=v(lock),
        commit=described,
        commit_version=v(version),
    )


def no_version_layer(name: str, lock: str, commit: str = "deadbeef") -> LayerVersions:
    """Build a layer whose recorded ``_commit`` yields no version."""
    return LayerVersions(
        name=name, lock_version=v(lock), commit=commit, commit_version=None
    )


def conflict(
    targets: Mapping[str, str], finished: Sequence[str], record_id: str = "2"
) -> MigrationRecord:
    """Build the ``conflict`` record of a walk paused after `finished`."""
    return MigrationRecord(
        id=record_id,
        from_version="app@1.0.0",
        to_version="app@1.1.0",
        timestamp=STAMP,
        status=MigrationStatus.CONFLICT,
        classification=ChangeClassification.MAJOR,
        targets=dict(targets),
        finished=tuple(finished),
    )


def success(record_id: str = "3") -> MigrationRecord:
    """Build a ``success`` record."""
    return MigrationRecord(
        id=record_id,
        from_version="app@1.0.0",
        to_version="app@1.1.0",
        timestamp=STAMP,
        status=MigrationStatus.SUCCESS,
        classification=ChangeClassification.MINOR,
    )
