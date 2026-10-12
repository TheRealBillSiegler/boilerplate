"""Tests for scripts/mkdocs_hooks.py, the docs build's MkDocs hooks.

``tests/`` has no ``__init__.py`` files anywhere, so this module loads the
script by path.
"""

import sys
from pathlib import Path

from mkdocs.config.defaults import MkDocsConfig

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from mkdocs_hooks import on_post_build


def _config_for(site_dir: Path) -> MkDocsConfig:
    """Return a build configuration whose site directory is ``site_dir``."""
    config = MkDocsConfig()
    config["site_dir"] = str(site_dir)
    return config


class TestDropsSearchLanguagePacks:
    """A built site loses the theme's search language packs and keeps the rest."""

    def test_deletes_the_language_packs(self, tmp_path: Path) -> None:
        packs = tmp_path / "assets" / "javascripts" / "lunr"
        (packs / "min").mkdir(parents=True)
        (packs / "min" / "lunr.de.min.js").write_text("// de", encoding="utf-8")
        (packs / "wordcut.js").write_text("// th", encoding="utf-8")

        on_post_build(config=_config_for(tmp_path))

        assert not packs.exists()

    def test_keeps_the_search_worker(self, tmp_path: Path) -> None:
        worker = tmp_path / "assets" / "javascripts" / "workers" / "search.min.js"
        worker.parent.mkdir(parents=True)
        worker.write_text("// worker", encoding="utf-8")
        (tmp_path / "assets" / "javascripts" / "lunr").mkdir()

        on_post_build(config=_config_for(tmp_path))

        assert worker.read_text(encoding="utf-8") == "// worker"


class TestSiteWithoutLanguagePacks:
    """A site the theme built without language packs comes out unchanged."""

    def test_leaves_the_site_alone(self, tmp_path: Path) -> None:
        (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")

        on_post_build(config=_config_for(tmp_path))

        assert [p.name for p in tmp_path.iterdir()] == ["index.html"]
