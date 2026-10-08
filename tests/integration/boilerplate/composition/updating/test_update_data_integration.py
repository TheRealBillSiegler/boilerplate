"""The update answer rule against real Copier updates on the made-up template family.

A layer's step takes an ancestor's question from the answers file of the ancestor
that declares it (design 04 §Safe Update), never from the layer's own copy.
"""

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


def test_declaring_ancestors_answer_beats_the_layers_stale_copy(
    family: Family, tmp_path: Path
) -> None:
    """The step passes the declaring ancestor's recorded answer as data.

    With core recording author_name 'Ada Probe' and service's file holding a
    stale copy, 'Own Name', updating service takes core's answer: data
    outranks the layer's own file, and the step rewrites that copy. The
    expected values come from design 04 (a descendant's stale copy of an
    ancestor's answer must not shadow the ancestor's value).
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
    commit_all(project, "service's copy of core's answer goes stale")
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
    } == {"core": AUTHOR, "service": AUTHOR}
