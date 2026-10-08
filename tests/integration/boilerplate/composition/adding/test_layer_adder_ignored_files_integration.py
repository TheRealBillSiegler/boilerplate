"""``LayerAdder`` names the ignored files a layer wrote and leaves them behind."""

import logging
from pathlib import Path

import pytest

from boilerplate.composition.adding import AddRequest, AddStatus, LayerAdder
from tests.integration.boilerplate.composition.adding.layers import build_layer
from tests.integration.boilerplate.composition.family import Family
from tests.integration.boilerplate.composition.scenarios.builders import (
    compose_locked_family,
)

IGNORED = "dist/generated.txt"


@pytest.fixture
def project(family: Family, tmp_path: Path) -> Path:
    """Compose core, whose ``.gitignore`` ignores ``dist/``, lock it and commit."""
    return compose_locked_family(family, tmp_path, "core", {"core": "1.0.0"})


def request(project: Path, name: str) -> AddRequest:
    return AddRequest(name=name, source=(project.parent / "repos" / name).as_posix())


class TestIgnoredFileTheLayerWrote:
    def test_outcome_and_log_name_the_path(
        self, project: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        build_layer(
            project.parent,
            "generated",
            files={IGNORED: "generated\n", "kept.txt": "kept\n"},
        )

        with caplog.at_level(logging.WARNING):
            outcome = LayerAdder().add(project, request(project, "generated"))

        assert outcome.status is AddStatus.ADDED
        assert [w for w in outcome.warnings if "dist/" in w] == [
            "Layer 'generated' wrote 'dist/', which .gitignore ignores; "
            "it is not carried into your checkout."
        ]
        assert any("dist/" in record.getMessage() for record in caplog.records)

    def test_the_ignored_file_is_not_carried(self, project: Path) -> None:
        build_layer(
            project.parent,
            "generated",
            files={IGNORED: "generated\n", "kept.txt": "kept\n"},
        )

        LayerAdder().add(project, request(project, "generated"))

        assert (project / "kept.txt").is_file()
        assert not (project / IGNORED).exists()

    def test_a_layer_with_no_ignored_file_warns_of_nothing(self, project: Path) -> None:
        build_layer(project.parent, "plain", files={"kept.txt": "kept\n"})

        outcome = LayerAdder().add(project, request(project, "plain"))

        assert outcome.warnings == ()
