"""A plain ``copier update`` of one git-backed layer: what it keeps and what it cannot.

The documented by-hand update (docs/templates-hub/plain-copier.md) is one
``copier update --answers-file .copier-answers.<layer>.yml`` per git-backed
layer; these tests mirror it through ``copier.run_update``, Copier's public API,
not the command line. The project is `service` over `core` of the made-up
family, composed at their first releases; `service` then gets a release that
edits a line rendering ``package_name``, a value `core` computes and no answers
file records. Two limits follow (ADR-015 points 1 and 4): the layer's answers
file is rewritten to the layer's own questions, and Copier renders the old copy
from that file alone, so a changed line that renders an inherited or computed
value conflicts unless the file carries the value. These scenarios are evidence
for those limits; see the scenarios README.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

import pytest
from copier import run_update

from tests.boilerplate.templates.conftest import commit_all, git, rehome_layer
from tests.integration.boilerplate.composition.family import Family
from tests.integration.boilerplate.composition.scenarios.builders import (
    answers_file,
    compose_family,
    copy_project,
)
from tests.integration.boilerplate.composition.temp_dir import temp_dir_inside

BASE = {"core": "1.0.0", "service": "1.0.0"}
ANSWERS_FILE = ".copier-answers.service.yml"
OLD_LINE = "docker build -t {{ package_name }} ."
NEW_LINE = "docker build -t {{ package_name }}:{{ port }} ."
CONFLICT_MARKER = "<<<<<<<"


class HandRunProject(NamedTuple):
    """A composed `service` over `core` whose service repository has a 1.3.0 tag."""

    project: Path
    repo: Path


@pytest.fixture(scope="module")
def base(
    family: Family, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[HandRunProject]:
    """Compose service over core at 1.0.0 against a service clone tagged 1.3.0."""
    work = tmp_path_factory.mktemp("hand-run-update")
    with temp_dir_inside(work):
        repo = work / "service-repo"
        git(
            work,
            "clone",
            "-q",
            "--no-hardlinks",
            family.repos["service"].as_posix(),
            repo.as_posix(),
        )
        template = repo / "SERVICE.md.jinja"
        template.write_text(
            template.read_text(encoding="utf-8").replace(OLD_LINE, NEW_LINE),
            encoding="utf-8",
            newline="\n",
        )
        commit_all(repo, "tag the image with its port", tag="1.3.0")
        project = compose_family(family, work, "service", BASE)
        rehome_layer(project, layer="service", source=repo, commit="1.0.0")
        commit_all(project, "rehome service")
        yield HandRunProject(project, repo)


def _update_by_hand(project: Path) -> None:
    """Mirror the documented service-layer ``copier update`` via ``run_update``."""
    run_update(
        project,
        answers_file=ANSWERS_FILE,
        vcs_ref="1.3.0",
        defaults=True,
        overwrite=True,
        unsafe=True,
        skip_tasks=True,
        quiet=True,
    )


def _service_md(project: Path) -> str:
    return (project / "SERVICE.md").read_text(encoding="utf-8")


@pytest.fixture()
def project(base: HandRunProject, tmp_path: Path) -> Path:
    """Return a private copy of the composed project."""
    return copy_project(base.project, tmp_path / "copy")


class TestAHandRunUpdateOfAGitBackedLayer:
    """Seam: Copier's public ``run_update``; truth: the lines the release edits."""

    def test_a_changed_line_that_renders_a_computed_value_conflicts(
        self, project: Path
    ) -> None:
        """The old copy lacks `package_name`, so `family_app` reads as a user edit."""
        _update_by_hand(project)

        assert CONFLICT_MARKER in _service_md(project)

    def test_the_conflict_is_one_block_in_the_edited_file(self, project: Path) -> None:
        _update_by_hand(project)

        assert _service_md(project).count(CONFLICT_MARKER) == 1

    def test_a_file_the_release_leaves_alone_gets_no_conflict(
        self, project: Path
    ) -> None:
        _update_by_hand(project)

        dockerfile = (project / "Dockerfile").read_text(encoding="utf-8")
        assert CONFLICT_MARKER not in dockerfile

    def test_the_answers_file_keeps_only_the_layers_own_questions(
        self, project: Path
    ) -> None:
        _update_by_hand(project)

        recorded = answers_file(project, "service")
        assert set(recorded) == {"_commit", "_src_path", "port", "python_version"}

    def test_the_value_in_the_answers_file_makes_the_update_clean(
        self, project: Path
    ) -> None:
        """A `package_name` in the file reaches the old copy, which `--data` cannot."""
        answers = project / ANSWERS_FILE
        with answers.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write("package_name: family_app\n")
        commit_all(project, "record the computed value for the update")

        _update_by_hand(project)

        assert "docker build -t family_app:8000 ." in _service_md(project)
        assert CONFLICT_MARKER not in _service_md(project)
