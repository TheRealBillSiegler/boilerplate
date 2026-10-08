"""``RenderEngine`` rendering the made-up family: one questionnaire, scoped layers.

The family's `app` layer extends `service` and `docs`; `docs` ships a
file-path Jinja filter that `app`'s own file uses, and `service` and `docs` are
siblings. Rendering `app` therefore shows both halves of the scoped render
loop: a layer's answers file records only its own and its ancestors' questions,
and an ancestor's file-path extension reaches the descendants that use it.
"""

from pathlib import Path

import pytest

from boilerplate.composition.rendering.engine import RenderEngine
from boilerplate.composition.rendering.models.execution_context import ExecutionContext
from tests.boilerplate.templates.conftest import compose
from tests.integration.boilerplate.composition.family import Family
from tests.integration.boilerplate.composition.scenarios.builders import (
    answers_file,
    lines,
    templates_at,
)

CORE_QUESTIONS = {
    "project_name",
    "author_name",
    "python_version",
    "use_tests",
}


@pytest.fixture()
def rendered(family: Family, tmp_path: Path) -> Path:
    """Render `app` at the first release of every layer through ``RenderEngine``."""
    templates = templates_at(
        family, tmp_path, {layer: tags[0] for layer, tags in family.tags.items()}
    )
    project = tmp_path / "project"
    RenderEngine().render(
        compose("app", templates),
        ExecutionContext(
            destination=project,
            context_data={"project_name": "Family App"},
            overwrite=True,
            interactive=False,
            skip_tasks=True,
        ),
    )
    return project


@pytest.mark.xdist_group("S19-family")
class TestFamilyThroughRenderEngine:
    """`app` renders through the engine the way `new` drives it."""

    def test_an_ancestors_file_path_filter_renders_in_the_descendant(
        self, rendered: Path
    ) -> None:
        """The engine registers docs' filter file for app's render."""
        assert (
            "The overview lives in the [documentation](docs/index.md#family-app)."
            in lines(rendered / "APP.md")
        )

    def test_the_root_layers_answers_file_records_only_its_own_questions(
        self, rendered: Path
    ) -> None:
        """Core is an ancestor of every layer and a descendant of none."""
        recorded = set(answers_file(rendered, "core"))

        assert recorded >= CORE_QUESTIONS
        assert recorded.isdisjoint({"port", "docs_generator", "docs_site_name"})

    def test_siblings_do_not_record_each_others_questions(self, rendered: Path) -> None:
        """Service records core's and its own questions, not docs'."""
        recorded = set(answers_file(rendered, "service"))

        assert {"port", "python_version"} <= recorded
        assert recorded.isdisjoint({"docs_generator", "docs_site_name"})
