"""``Updater`` names the ignored files a layer's update wrote and leaves them behind."""

import logging
from pathlib import Path

import pytest

from boilerplate.composition.adding import AddRequest, LayerAdder
from boilerplate.composition.updating import Updater, UpdateRequest
from boilerplate.composition.updating.update_status import UpdateStatus
from tests.boilerplate.templates.conftest import commit_all
from tests.integration.boilerplate.composition.adding.layers import build_layer
from tests.integration.boilerplate.composition.family import Family
from tests.integration.boilerplate.composition.scenarios.builders import (
    compose_locked_family,
)

pytestmark = [pytest.mark.scenario]


@pytest.fixture
def project(family: Family, tmp_path: Path) -> Path:
    """Compose core, add the one-off layer ``gen`` at 1.0.0 and commit the result.

    Release 1.1.0 of ``gen`` then adds a file under core's ignored ``dist/``.
    """
    project = compose_locked_family(family, tmp_path, "core", {"core": "1.0.0"})
    repo = build_layer(tmp_path, "gen", files={"kept.txt": "one\n"})
    LayerAdder().add(project, AddRequest(name="gen", source=repo.as_posix()))
    commit_all(project, "add gen")
    meta = repo / "boilerplate.yml"
    meta.write_text(
        meta.read_text(encoding="utf-8").replace("1.0.0", "1.1.0"), encoding="utf-8"
    )
    (repo / "dist").mkdir()
    (repo / "dist" / "generated.txt").write_text("generated\n", encoding="utf-8")
    (repo / "kept.txt").write_text("two\n", encoding="utf-8")
    commit_all(repo, "release 1.1.0", "1.1.0")
    return project


class TestIgnoredFileTheUpdateWrote:
    def test_outcome_and_log_name_the_path(
        self, project: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING):
            outcome = Updater().update(
                project, UpdateRequest(targets={"core": "1.0.0", "gen": "1.1.0"})
            )

        assert outcome.status is UpdateStatus.UPDATED
        assert [w for w in outcome.warnings if "dist/" in w] == [
            "Layer 'gen' wrote 'dist/', which .gitignore ignores; "
            "it is not carried into your checkout."
        ]
        assert any("dist/" in record.getMessage() for record in caplog.records)

    def test_the_ignored_file_is_not_carried_and_the_rest_is(
        self, project: Path
    ) -> None:
        Updater().update(
            project, UpdateRequest(targets={"core": "1.0.0", "gen": "1.1.0"})
        )

        assert (project / "kept.txt").read_text(encoding="utf-8") == "two\n"
        assert not (project / "dist" / "generated.txt").exists()
