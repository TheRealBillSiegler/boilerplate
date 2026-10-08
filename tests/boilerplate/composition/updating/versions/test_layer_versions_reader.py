"""Tests for reading each layer's versions in layer_versions_reader.py."""

from datetime import UTC, datetime
from pathlib import Path

from packaging.version import Version

from boilerplate.composition.updating.versions import read_layer_versions
from boilerplate.models import BoilerplateLock, LockLayer
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
    (project / f".copier-answers.{layer}.yml").write_text(text, encoding="utf-8")


class TestReadLayerVersions:
    """Each layer's entry joins the lock, the graph and the answers file."""

    def test_follows_the_locks_layer_order_and_carries_its_versions(
        self, tmp_path: Path
    ) -> None:
        lock = _lock(("core", "1.0.0"), ("service", "1.1.0"))

        layers = read_layer_versions(tmp_path, lock, {"service": ["core"]})

        assert [layer.name for layer in layers] == ["core", "service"]
        assert [str(layer.lock_version) for layer in layers] == ["1.0.0", "1.1.0"]

    def test_names_each_layers_ancestors(self, tmp_path: Path) -> None:
        lock = _lock(("core", "1.0.0"), ("service", "1.0.0"))

        layers = read_layer_versions(tmp_path, lock, {"service": ["core"]})

        assert [layer.ancestors for layer in layers] == [(), ("core",)]

    def test_records_the_commit_the_answers_file_holds(self, tmp_path: Path) -> None:
        _answers(tmp_path, "core", "_commit: 1.0.0\n_src_path: somewhere\n")

        (core,) = read_layer_versions(tmp_path, _lock(("core", "1.0.0")), {})

        assert core.commit == "1.0.0"

    def test_a_layer_without_an_answers_file_records_no_commit(
        self, tmp_path: Path
    ) -> None:
        (core,) = read_layer_versions(tmp_path, _lock(("core", "1.0.0")), {})

        assert core.commit is None
        assert core.commit_version is None

    def test_a_commit_without_a_source_yields_no_version(self, tmp_path: Path) -> None:
        _answers(tmp_path, "core", "_commit: 1.0.0\n")

        (core,) = read_layer_versions(tmp_path, _lock(("core", "1.0.0")), {})

        assert core.commit == "1.0.0"
        assert core.commit_version is None

    def test_a_source_that_is_not_a_git_repository_yields_no_version(
        self, tmp_path: Path
    ) -> None:
        source = tmp_path / "plain-template"
        source.mkdir()
        _answers(tmp_path, "core", f"_commit: 1.0.0\n_src_path: {source.as_posix()}\n")

        (core,) = read_layer_versions(tmp_path, _lock(("core", "1.0.0")), {})

        assert core.commit == "1.0.0"
        assert core.commit_version is None


class TestReadLayerVersionsThroughAGivenReader:
    """A caller that already holds the releases reads versions from them."""

    def test_the_commit_is_read_as_the_version_the_reader_gives(
        self, tmp_path: Path
    ) -> None:
        """Ask the reader for the layer's recorded source and commit."""
        _answers(tmp_path, "core", "_commit: 1.0.0-2-gabc\n_src_path: somewhere\n")
        asked: list[tuple[str, str]] = []

        def reader(source: str, commit: str) -> Version | None:
            asked.append((source, commit))
            return Version("1.0.0.post2")

        (core,) = read_layer_versions(
            tmp_path, _lock(("core", "1.0.0")), {}, version_reader=reader
        )

        assert (asked, core.commit_version) == (
            [("somewhere", "1.0.0-2-gabc")],
            SerializableVersion("1.0.0.post2"),
        )
