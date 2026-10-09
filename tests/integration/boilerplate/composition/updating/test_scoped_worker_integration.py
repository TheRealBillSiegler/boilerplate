"""``ScopedWorker`` against real Copier updates on the made-up template family.

Copier renders an update three times: an old copy at the recorded ref, the
project in place and a new copy at the target ref, then applies the
old-to-new diff. ``ScopedWorker`` builds each render's template from the view
keyed by the ref that render sets on it. These tests pin which inputs reach
which render when core drops `use_tests` between 2.1.0 and 3.0.0.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

import pytest

from tests.boilerplate.templates.conftest import recorded_answers
from tests.integration.boilerplate.composition.family import Family
from tests.integration.boilerplate.composition.scenarios.builders import (
    Recording,
    compose_family,
    recording_worker,
    update_family_layer,
)
from tests.integration.boilerplate.composition.temp_dir import temp_dir_inside

pytestmark = [pytest.mark.scenario]

REMOVAL_FILE = "tests/test_smoke.py"
REMOVAL_BEFORE = {"core": "2.1.0", "service": "1.0.0"}
REMOVAL_AFTER = {"core": "3.0.0", "service": "1.0.0"}


class RemovalUpdate(NamedTuple):
    """Core updated 2.1.0 to 3.0.0, which drops `use_tests`, with data={}."""

    project: Path
    recording: Recording


@pytest.fixture(scope="module")
def removal(
    family: Family, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[RemovalUpdate]:
    """Compose with `use_tests` off at core 2.1.0, then update core with data={}."""
    work = tmp_path_factory.mktemp("removal")
    with temp_dir_inside(work):
        project = compose_family(
            family, work, "service", REMOVAL_BEFORE, {"use_tests": False}
        )
        worker, recording = recording_worker([REMOVAL_FILE])
        update_family_layer(
            family,
            project,
            root="service",
            layer="core",
            before=REMOVAL_BEFORE,
            after=REMOVAL_AFTER,
            work=work,
            data={},
            worker_type=worker,
        )
        yield RemovalUpdate(project, recording)


@pytest.mark.xdist_group("mechanics-removal")
class TestEachCopyRendersItsOwnRelease:
    """S12 control: what reaches the old copy, and which view each copy renders."""

    def test_old_copy_renders_from_the_answers_file_not_data(
        self, removal: RemovalUpdate
    ) -> None:
        """S12 control: with data={} the old copy still renders the recorded answer.

        Copier builds the old copy's answers from the layer's answers file, so
        nothing forced through ``data`` reaches it: with `use_tests` recorded
        off, the old copy has no smoke test, where the default would write one.
        """
        assert removal.recording.copies["old_copy"][REMOVAL_FILE] is None

    def test_each_render_builds_its_template_from_its_own_refs_view(
        self, removal: RemovalUpdate
    ) -> None:
        """S12: Copier sets each rebuilt worker's ref; each builds that ref's view.

        The update builds a template for its checks, the old copy at the
        recorded 2.1.0, the in-place render and the new copy at the target 3.0.0.
        """
        assert removal.recording.builds == [
            ("in_place", "3.0.0"),
            ("old_copy", "2.1.0"),
            ("in_place", "3.0.0"),
            ("new_copy", "3.0.0"),
        ]


def test_forced_data_never_reaches_the_old_copy(family: Family, tmp_path: Path) -> None:
    """Data forced into an update renders in place and in the new copy only.

    Forcing project_name 'FORCED' over the recorded one, the old copy's
    pyproject.toml still renders the recorded name. This checks the S12
    control's reading directly.
    """
    project = compose_family(family, tmp_path, "service", REMOVAL_BEFORE)
    worker, recording = recording_worker(["pyproject.toml"])
    update_family_layer(
        family,
        project,
        root="service",
        layer="core",
        before=REMOVAL_BEFORE,
        after=REMOVAL_AFTER,
        work=tmp_path,
        data={**recorded_answers(project, "core"), "project_name": "FORCED"},
        worker_type=worker,
    )
    descriptions = {
        role: next(
            line
            for line in (recording.copies[role]["pyproject.toml"] or "").splitlines()
            if line.startswith("description")
        )
        for role in ("old_copy", "new_copy")
    }

    assert descriptions == {
        "old_copy": 'description = "Family App"',
        "new_copy": 'description = "FORCED"',
    }
