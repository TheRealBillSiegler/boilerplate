"""Where each layer of a project fetches its template from."""

from datetime import UTC, datetime
from pathlib import Path

from boilerplate.composition.updating.walk.layer_sources import read_layer_sources
from boilerplate.models import BoilerplateLock, LockLayer
from boilerplate.types import SerializableVersion

STAMP = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)


def lock_of(*layers: str) -> BoilerplateLock:
    """Build a lock whose layers record the source ``lock/<name>``."""
    return BoilerplateLock(
        boilerplate_version="0.3.0",
        copier_version="9.18.1",
        created_at=STAMP,
        updated_at=STAMP,
        root_template=f"{layers[-1]}@1.0.0",
        layers=tuple(
            LockLayer(
                name=name,
                version=SerializableVersion("1.0.0"),
                source=f"lock/{name}",
                checksum="sha256:" + "a" * 64,
            )
            for name in layers
        ),
    )


class TestReadLayerSources:
    def test_takes_the_source_the_answers_file_records(self, tmp_path: Path) -> None:
        """Update from the source Copier will update from."""
        (tmp_path / ".copier-answers.core.yml").write_text(
            "_src_path: /repos/core\n", encoding="utf-8"
        )

        assert read_layer_sources(tmp_path, lock_of("core")) == {"core": "/repos/core"}

    def test_falls_back_to_the_locks_source(self, tmp_path: Path) -> None:
        """Use the lock's source for a layer whose file records none."""
        assert read_layer_sources(tmp_path, lock_of("core")) == {"core": "lock/core"}

    def test_follows_the_locks_layer_order(self, tmp_path: Path) -> None:
        """List the layers as the lock does."""
        assert list(read_layer_sources(tmp_path, lock_of("core", "app"))) == [
            "core",
            "app",
        ]
