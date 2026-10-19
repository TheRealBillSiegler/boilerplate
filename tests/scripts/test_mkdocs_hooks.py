"""Tests for scripts/mkdocs_hooks.py, the docs build's MkDocs hooks.

``tests/`` has no ``__init__.py`` files anywhere, so this module loads the
script by path.
"""

import html
import re
import sys
from pathlib import Path

import pytest
from mkdocs.config.defaults import MkDocsConfig

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from mkdocs_hooks import on_page_content, on_post_build


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


def _task_item(text_html: str, *, checked: bool = False) -> str:
    """Return the markup pymdownx.tasklist renders for one item."""
    state = " checked" if checked else ""
    return (
        '<li class="task-list-item"><label class="task-list-control">'
        f'<input type="checkbox" disabled{state}/>'
        f'<span class="task-list-indicator"></span></label> {text_html}</li>'
    )


def _labels(page_html: str) -> list[str]:
    """Return the decoded aria-label of every checkbox in ``page_html``."""
    return [
        html.unescape(label)
        for label in re.findall(r'<input\b[^>]*\baria-label="([^"]*)"', page_html)
    ]


class TestLabelsTaskListCheckboxes:
    """Each task-list checkbox is named by the text of its own item."""

    def test_names_the_checkbox_by_the_item_text(self) -> None:
        page = f'<ul class="task-list">{_task_item("Item text")}</ul>'

        assert _labels(on_page_content(page)) == ["Item text"]

    def test_names_each_item_by_its_own_text(self) -> None:
        page = "<ul>" + _task_item("First") + _task_item("Second") + "</ul>"

        assert _labels(on_page_content(page)) == ["First", "Second"]

    def test_uses_the_text_content_of_inline_markup(self) -> None:
        item = _task_item('Bump <code>MAJOR</code> in <a href="x/">the file</a>')

        assert _labels(on_page_content(f"<ul>{item}</ul>")) == [
            "Bump MAJOR in the file"
        ]

    def test_decodes_and_escapes_entities(self) -> None:
        item = _task_item('Tom &amp; "Jerry" &lt;3')

        labelled = on_page_content(f"<ul>{item}</ul>")

        assert _labels(labelled) == ['Tom & "Jerry" <3']
        assert 'aria-label="Tom &amp; &quot;Jerry&quot; &lt;3"' in labelled

    def test_excludes_a_nested_list_from_the_parent_name(self) -> None:
        nested = _task_item("Child")
        item = _task_item(f"Parent<ul>{nested}</ul>")

        assert _labels(on_page_content(f"<ul>{item}</ul>")) == ["Parent", "Child"]

    def test_keeps_the_checked_state(self) -> None:
        labelled = on_page_content("<ul>" + _task_item("Done", checked=True) + "</ul>")

        assert "disabled checked" in labelled
        assert _labels(labelled) == ["Done"]

    @pytest.mark.parametrize("separator", ["\x0c", "\u2028"])
    def test_counts_lines_by_newline_only(self, separator: str) -> None:
        item = _task_item("Do it")
        page = f"<pre>a{separator}b</pre>\n<ul>{item}</ul>"

        labelled = on_page_content(page)

        assert _labels(labelled) == ["Do it"]
        assert '<label class="task-list-control">' in labelled


class TestLeavesOtherMarkupAlone:
    """Only task-list checkboxes change; every other page comes out unchanged."""

    def test_a_page_without_task_lists_is_unchanged(self) -> None:
        page = "<p>Hello</p><ul><li>One</li></ul>"

        assert on_page_content(page) == page

    def test_a_checkbox_outside_a_task_item_is_unchanged(self) -> None:
        page = '<li><input type="checkbox"/> Plain</li>'

        assert on_page_content(page) == page

    def test_a_checkbox_that_already_has_a_label_keeps_it(self) -> None:
        page = (
            '<ul><li class="task-list-item"><label class="task-list-control">'
            '<input type="checkbox" aria-label="Mine" disabled/>'
            '<span class="task-list-indicator"></span></label> Other</li></ul>'
        )

        assert on_page_content(page) == page
