"""Rendered projects do not contain template-authoring metadata.

Renders the real, shipped multi-layer `streamlit` composition (streamlit
extends project) end to end — no mocked Copier Worker — because the bug this
guards against lives in Copier's own exclude-merging behavior, not in
boilerplate's orchestration code.
"""

from pathlib import Path

import pytest

from boilerplate.cli.utils import build_template_catalog
from boilerplate.composition import Composer
from boilerplate.composition.rendering.engine import RenderEngine
from boilerplate.composition.rendering.models.execution_context import (
    ExecutionContext,
)
from boilerplate.composition.resolution import Resolver
from boilerplate.settings import Settings


def _render_streamlit(tmp_path: Path) -> Path:
    registry = build_template_catalog(None, Settings())
    resolution = Resolver().resolve("streamlit", registry)
    composition = Composer().compose(resolution)
    dest = tmp_path / "out"
    ctx = ExecutionContext(
        destination=dest,
        context_data={},
        overwrite=True,
        interactive=False,
        skip_tasks=True,
    )
    RenderEngine().render(composition, ctx)
    return dest


class TestAuthoringMetadataExcluded:
    def test_no_boilerplate_yml_or_copier_yml_at_root_of_output(self, tmp_path: Path):
        dest = _render_streamlit(tmp_path)

        assert not (dest / "boilerplate.yml").exists()
        assert not (dest / "copier.yml").exists()

    def test_templates_own_exclude_entries_still_apply(self, tmp_path: Path):
        """The project layer's own `_exclude: [_extensions]` keeps working.

        Injecting boilerplate.yml/copier.yml into the exclude set must union
        with a layer's own `_exclude`, never replace it.
        """
        dest = _render_streamlit(tmp_path)

        assert not (dest / "_extensions").exists()


class TestAuthoringMetadataExclusionIsRootOnly:
    """The exclude patterns anchor to the layer root rather than matching at any depth.

    Uses a hand-built single-layer template (not the shipped ones, and not the
    `templates_dir_factory` conftest fixture — that fixture wraps questions
    under a `questions:` key, which Composer treats as a literal top-level
    question rather than a schema, breaking a real render) because no shipped
    template currently ships nested files named `copier.yml`/`boilerplate.yml`
    — an unanchored pattern would pass the `TestAuthoringMetadataExcluded`
    checks above while still stripping a template author's legitimate nested
    content.
    """

    @pytest.fixture()
    def rendered_with_nested_metadata_names(self, tmp_path: Path) -> Path:
        root = tmp_path / "templates_root"
        tpl_dir = root / "roottest"
        tpl_dir.mkdir(parents=True)
        (tpl_dir / "boilerplate.yml").write_text(
            "name: roottest\nversion: 1.0.0\n", encoding="utf-8"
        )
        # `_exclude: []` disables Copier's own DEFAULT_EXCLUDE (which,
        # unrelated to this fix, unanchored-matches `copier.yml` at any
        # depth) so this test isolates boilerplate's injected excludes.
        (tpl_dir / "copier.yml").write_text("_exclude: []\n", encoding="utf-8")

        nested = tpl_dir / "docs"
        nested.mkdir()
        (nested / "copier.yml").write_text("nested: true\n", encoding="utf-8")
        (nested / "boilerplate.yml").write_text("nested: true\n", encoding="utf-8")
        (tpl_dir / "keep.txt").write_text("keep me\n", encoding="utf-8")

        registry = build_template_catalog(root, Settings())
        resolution = Resolver().resolve("roottest", registry)
        composition = Composer().compose(resolution)
        dest = tmp_path / "out"
        ctx = ExecutionContext(
            destination=dest,
            context_data={},
            overwrite=True,
            interactive=False,
            skip_tasks=True,
        )
        RenderEngine().render(composition, ctx)
        return dest

    def test_root_metadata_still_excluded(
        self, rendered_with_nested_metadata_names: Path
    ):
        dest = rendered_with_nested_metadata_names

        assert not (dest / "boilerplate.yml").exists()
        assert not (dest / "copier.yml").exists()

    def test_nested_files_sharing_the_metadata_names_survive(
        self, rendered_with_nested_metadata_names: Path
    ):
        dest = rendered_with_nested_metadata_names

        assert (dest / "docs" / "copier.yml").exists()
        assert (dest / "docs" / "boilerplate.yml").exists()
        assert (dest / "keep.txt").exists()
