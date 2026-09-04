"""Composing the real bundled `streamlit` (extends `project`) template.

Proves the per-layer answers-file contract end to end against the actual
shipped templates, not test-only fixtures: each layer's own `copier.yml`
`_answers_file` declaration and answers-file stub produce that layer's own
`.copier-answers.<layer>.yml`, and no canonical `.copier-answers.yml` is
written by Boilerplate. See docs/design/adr-015-idiomatic-artifacts.md.
"""

from pathlib import Path

import yaml

from boilerplate.catalog import TemplateCatalog
from boilerplate.composition import Composer, Resolver
from boilerplate.composition.rendering.engine import RenderEngine
from boilerplate.composition.rendering.models.execution_context import ExecutionContext


def _render(name: str, catalog: TemplateCatalog, destination: Path) -> None:
    """Render `name` from `catalog` into `destination` with defaults, no tasks."""
    resolution = Resolver().resolve(name, catalog)
    composition = Composer().compose(resolution)
    ctx = ExecutionContext(
        destination=destination,
        overwrite=True,
        interactive=False,
        skip_tasks=True,
    )
    RenderEngine().render(composition, ctx)


class TestBundledComposedAnswersFiles:
    def test_each_layer_gets_its_own_answers_file(
        self, integration_catalog: TemplateCatalog, tmp_path: Path
    ) -> None:
        destination = tmp_path / "generated"

        _render("streamlit", integration_catalog, destination)

        project_answers = yaml.safe_load(
            (destination / ".copier-answers.project.yml").read_text(encoding="utf-8")
        )
        assert project_answers["_src_path"]

        streamlit_answers = yaml.safe_load(
            (destination / ".copier-answers.streamlit.yml").read_text(encoding="utf-8")
        )
        assert streamlit_answers["_src_path"]

        assert not (destination / ".copier-answers.yml").exists()
