"""The update answer rule against real Copier updates on the made-up template family."""

from pathlib import Path

import pytest

from tests.boilerplate.templates.conftest import commit_all, recorded_answers
from tests.integration.boilerplate.composition.family import Family
from tests.integration.boilerplate.composition.scenarios.builders import (
    AUTHOR,
    compose_family,
    substitute,
    update_family_layer,
)

pytestmark = [pytest.mark.scenario]


def test_layers_own_recorded_answer_beats_its_ancestors(
    family: Family, tmp_path: Path
) -> None:
    """The scoped data lays the layer's own answers over its ancestors'.

    With core recording author_name 'Ada Probe' and service 'Own Name',
    updating service keeps 'Own Name'. This checks the layering rule through
    Copier's recording.
    """
    before = {"core": "1.0.0", "service": "1.0.0"}
    project = compose_family(
        family, tmp_path, "service", before, {"author_name": AUTHOR}
    )
    substitute(
        project / ".copier-answers.service.yml",
        f"author_name: {AUTHOR}\n",
        "author_name: Own Name\n",
    )
    commit_all(project, "service's answer diverges from core's")
    update_family_layer(
        family,
        project,
        root="service",
        layer="service",
        before=before,
        after={**before, "service": "1.1.0"},
        work=tmp_path,
    )

    assert {
        layer: recorded_answers(project, layer)["author_name"]
        for layer in ("core", "service")
    } == {"core": AUTHOR, "service": "Own Name"}
