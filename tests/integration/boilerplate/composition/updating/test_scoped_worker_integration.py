"""``ScopedWorker`` against real Copier updates on the made-up template family.

Copier renders an update three times: an old copy at the recorded ref, the
project in place and a new copy at the target ref, then applies the
old-to-new diff. ``ScopedWorker`` builds each render's template from the old
view for the old copy and the target view for the other two. These tests pin
which inputs reach which render when core drops `use_tests` between 2.1.0 and
3.0.0, and when only an ancestor moves.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

import pytest

from boilerplate.composition.views import LayerView
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


ANCESTOR_BEFORE = {"core": "1.0.0", "service": "1.0.0", "docs": "1.0.0", "app": "1.0.0"}
ANCESTOR_AFTER = {**ANCESTOR_BEFORE, "docs": "1.1.0"}


def _validator(view: LayerView) -> object:
    """Return the validator the view's `docs_site_name` question carries."""
    return view.questions["docs_site_name"].get("validator")


@pytest.mark.xdist_group("mechanics-ancestor-only")
class TestAncestorOnlyMove:
    """Docs moves 1.0.0 to 1.1.0 while app's own ref stays 1.0.0.

    Docs 1.1.0 adds a validator to `docs_site_name`, so app's view differs
    between the recorded release and the target although app's ref is the same
    in the old copy, the in-place render and the new copy.
    """

    @pytest.fixture(scope="class")
    def recording(
        self, family: Family, tmp_path_factory: pytest.TempPathFactory
    ) -> Iterator[Recording]:
        """Update app with docs moved and record the view each render built from."""
        work = tmp_path_factory.mktemp("ancestor-only")
        with temp_dir_inside(work):
            project = compose_family(family, work, "app", ANCESTOR_BEFORE)
            worker, recording = recording_worker()
            update_family_layer(
                family,
                project,
                root="app",
                layer="app",
                before=ANCESTOR_BEFORE,
                after=ANCESTOR_AFTER,
                work=work,
                worker_type=worker,
            )
            yield recording

    def test_old_copy_builds_from_the_recorded_releases_view(
        self, recording: Recording
    ) -> None:
        """Give the old copy the questionnaire docs had at 1.0.0."""
        assert {
            role: _validator(view) is not None
            for role, view in recording.views
            if role == "old_copy"
        } == {"old_copy": False}

    @pytest.mark.parametrize("role", ["in_place", "new_copy"])
    def test_in_place_and_new_copy_build_from_the_target_view(
        self, recording: Recording, role: str
    ) -> None:
        """Give the renders at the target the questionnaire docs has at 1.1.0."""
        assert {
            _validator(view) is not None for r, view in recording.views if r == role
        } == {True}
