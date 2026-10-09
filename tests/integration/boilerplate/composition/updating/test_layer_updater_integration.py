"""``update_layer`` against a real Copier update of the made-up template family.

Core moves from 2.1.0 to 3.0.0, the release the family stores for it. The
answers file Copier writes is the observable: it records the release the
layer now sits at and the answers the update forced.
"""

from pathlib import Path

import pytest
from copier.errors import UnsafeTemplateError

from boilerplate.composition.updating import (
    LayerRelease,
    StepInputs,
    UpdateViews,
    read_recorded_answers_by_layer,
    update_layer,
)
from tests.boilerplate.templates.conftest import layer_view
from tests.integration.boilerplate.composition.family import Family
from tests.integration.boilerplate.composition.scenarios.builders import (
    answers_file,
    compose_family,
    templates_at,
)

pytestmark = [pytest.mark.scenario]

BEFORE = {"core": "2.1.0", "service": "1.0.0"}
AFTER = {"core": "3.0.0", "service": "1.0.0"}


def _update_core(
    family: Family,
    project: Path,
    work: Path,
    *,
    needs_unsafe: bool = True,
    **data: str,
) -> None:
    update_layer(
        project,
        LayerRelease(
            layer="core", source=family.repos["core"].as_posix(), ref=AFTER["core"]
        ),
        UpdateViews(
            layer_view("core", templates_at(family, work, BEFORE)),
            layer_view("core", templates_at(family, work, AFTER)),
            needs_unsafe=needs_unsafe,
        ),
        StepInputs(supplied=data, walk_answers=read_recorded_answers_by_layer(project)),
    )


class TestUpdateLayer:
    def test_answers_file_records_the_target_release(
        self, family: Family, tmp_path: Path
    ) -> None:
        project = compose_family(family, tmp_path, "service", BEFORE)

        _update_core(family, project, tmp_path)

        assert answers_file(project, "core")["_commit"] == AFTER["core"]

    def test_forced_data_reaches_the_updated_layer(
        self, family: Family, tmp_path: Path
    ) -> None:
        project = compose_family(family, tmp_path, "service", BEFORE)

        _update_core(family, project, tmp_path, project_name="FORCED")

        assert answers_file(project, "core")["project_name"] == "FORCED"


class TestUnsafeGrant:
    """The step grants Copier's ``unsafe`` only when its views say it is needed."""

    def test_a_step_that_needs_no_grant_leaves_copiers_consent_gate_closed(
        self, family: Family, tmp_path: Path
    ) -> None:
        """Core declares extensions, tasks and migrations, so Copier refuses it."""
        project = compose_family(family, tmp_path, "service", BEFORE)

        with pytest.raises(UnsafeTemplateError):
            _update_core(family, project, tmp_path, needs_unsafe=False)
