"""In a composed render, no layer's `_skip_if_exists` applies.

Composition overlays layers in order: `new streamlit` renders `project` then
`streamlit` into the same destination, and the streamlit layer's file at a
shared path (`README.md`) is meant to win (docs/design/04-composition-engine.md
§Per-Layer Render Loop). A composed render writes every layer's files
regardless of what it declares; a layer's `_skip_if_exists` list governs only
that layer's own `copier update`. Without this rule, overlay stops working the
moment both layers declare the shared file project-owned.
"""

from pathlib import Path

from tests.boilerplate.templates.conftest import render


class TestSharedFileOverlayIgnoresSkipIfExistsWithinOneRender:
    def test_new_streamlit_ends_with_the_streamlit_readme(self, tmp_path: Path) -> None:
        dest = render("streamlit", tmp_path)

        readme = (dest / "README.md").read_text(encoding="utf-8")

        assert "## Run" in readme, "the streamlit layer's own README section"
        assert "## Quick start" not in readme, "the project layer's README lost"
