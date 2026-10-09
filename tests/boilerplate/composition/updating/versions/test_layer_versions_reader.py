"""Tests for reading each layer's versions in layer_versions_reader.py."""

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from boilerplate.composition.updating.versions import read_layer_versions
from boilerplate.models import BoilerplateLock, LockLayer
from boilerplate.project_state.answers_file import answers_file_name
from boilerplate.repository.release_checkouts import ReleaseCheckouts
from boilerplate.types import SerializableVersion

STAMP = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
CHECKSUM = "sha256:" + "a" * 64


def _lock(*layers: tuple[str, str]) -> BoilerplateLock:
    return BoilerplateLock(
        boilerplate_version="0.3.0",
        copier_version="9.18.1",
        created_at=STAMP,
        updated_at=STAMP,
        root_template="service@1.0.0",
        layers=tuple(
            LockLayer(
                name=name,
                version=SerializableVersion(version),
                source="unused",
                checksum=CHECKSUM,
            )
            for name, version in layers
        ),
    )


def _answers(project: Path, layer: str, text: str) -> None:
    (project / answers_file_name(layer)).write_text(text, encoding="utf-8")


@pytest.fixture
def checkouts() -> Iterator[ReleaseCheckouts]:
    """Return the release checkouts the reader reads versions from."""
    with ReleaseCheckouts() as held:
        yield held


class TestReadLayerVersions:
    """Each layer's entry joins the lock, the graph and the answers file."""

    def test_follows_the_locks_layer_order_and_carries_its_versions(
        self, tmp_path: Path, checkouts: ReleaseCheckouts
    ) -> None:
        lock = _lock(("core", "1.0.0"), ("service", "1.1.0"))

        layers = read_layer_versions(tmp_path, lock, {"service": ["core"]}, checkouts)

        assert [layer.name for layer in layers] == ["core", "service"]
        assert [str(layer.lock_version) for layer in layers] == ["1.0.0", "1.1.0"]

    def test_names_each_layers_ancestors(
        self, tmp_path: Path, checkouts: ReleaseCheckouts
    ) -> None:
        lock = _lock(("core", "1.0.0"), ("service", "1.0.0"))

        layers = read_layer_versions(tmp_path, lock, {"service": ["core"]}, checkouts)

        assert [layer.ancestors for layer in layers] == [(), ("core",)]

    def test_records_the_commit_the_answers_file_holds(
        self, tmp_path: Path, checkouts: ReleaseCheckouts
    ) -> None:
        source = tmp_path / "plain-template"
        source.mkdir()
        _answers(tmp_path, "core", f"_commit: 1.0.0\n_src_path: {source.as_posix()}\n")

        (core,) = read_layer_versions(tmp_path, _lock(("core", "1.0.0")), {}, checkouts)

        assert core.commit == "1.0.0"

    def test_a_layer_without_an_answers_file_records_no_commit(
        self, tmp_path: Path, checkouts: ReleaseCheckouts
    ) -> None:
        (core,) = read_layer_versions(tmp_path, _lock(("core", "1.0.0")), {}, checkouts)

        assert core.commit is None
        assert core.commit_version is None

    def test_a_commit_without_a_source_yields_no_version(
        self, tmp_path: Path, checkouts: ReleaseCheckouts
    ) -> None:
        _answers(tmp_path, "core", "_commit: 1.0.0\n")

        (core,) = read_layer_versions(tmp_path, _lock(("core", "1.0.0")), {}, checkouts)

        assert core.commit == "1.0.0"
        assert core.commit_version is None

    def test_a_source_that_is_not_a_git_repository_yields_no_version(
        self, tmp_path: Path, checkouts: ReleaseCheckouts
    ) -> None:
        source = tmp_path / "plain-template"
        source.mkdir()
        _answers(tmp_path, "core", f"_commit: 1.0.0\n_src_path: {source.as_posix()}\n")

        (core,) = read_layer_versions(tmp_path, _lock(("core", "1.0.0")), {}, checkouts)

        assert core.commit == "1.0.0"
        assert core.commit_version is None
