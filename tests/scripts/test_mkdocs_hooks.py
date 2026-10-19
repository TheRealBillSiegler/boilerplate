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


def _panzoom_box(*, full_screen: bool = True) -> str:
    """Return the markup mkdocs-panzoom-plugin wraps around a diagram.

    The shape matches the plugin's own ``create_panzoom_box``, with the icon
    paths shortened.
    """
    icon = (
        '<svg class="panzoom-icon" viewBox="0 0 512 512" '
        'xmlns="http://www.w3.org/2000/svg"><path d="M0 0"></path></svg>'
    )
    full_screen_buttons = (
        f'<button class="panzoom-max panzoom-button">{icon}</button>'
        f'<button class="panzoom-min panzoom-button panzoom-hidden">{icon}</button>'
        if full_screen
        else ""
    )
    return (
        '<div class="panzoom-box" data-key="alt" id="panzoom0">'
        '<nav class="panzoom-nav">'
        f'<button class="panzoom-info panzoom-button">{icon}</button>'
        f'<button class="panzoom-reset panzoom-button">{icon}</button>'
        f"{full_screen_buttons}</nav>"
        '<div class="mermaid">graph</div></div>'
    )


def _button_labels(page_html: str) -> dict[str, str]:
    """Return each panzoom button's aria-label, keyed by its action class."""
    return dict(
        re.findall(
            r'<button class="panzoom-(\w+) [^>]*\baria-label="([^"]*)"', page_html
        )
    )


class TestNamesPanzoomControls:
    """Each diagram control is named for what it does and hides its icon."""

    def test_names_each_button_by_its_action(self) -> None:
        labelled = on_page_content(_panzoom_box())

        assert _button_labels(labelled) == {
            "info": "Show pan and zoom help",
            "reset": "Reset zoom",
            "max": "Enter full screen",
            "min": "Exit full screen",
        }

    def test_names_only_the_buttons_the_page_renders(self) -> None:
        labelled = on_page_content(_panzoom_box(full_screen=False))

        assert sorted(_button_labels(labelled)) == ["info", "reset"]

    def test_hides_every_icon_from_assistive_technology(self) -> None:
        labelled = on_page_content(_panzoom_box())

        icons = re.findall(r'<svg class="panzoom-icon"[^>]*>', labelled)

        assert len(icons) == 4
        assert all('aria-hidden="true"' in icon for icon in icons)
        assert all('focusable="false"' in icon for icon in icons)

    def test_names_the_controls_landmark(self) -> None:
        labelled = on_page_content(_panzoom_box())

        assert '<nav class="panzoom-nav" aria-label="Diagram controls">' in labelled

    def test_names_a_landmark_with_extra_classes(self) -> None:
        page = '<nav class="panzoom-nav panzoom-top-nav"></nav>'

        assert on_page_content(page) == (
            '<nav class="panzoom-nav panzoom-top-nav" aria-label="Diagram controls">'
            "</nav>"
        )

    def test_names_each_diagram_on_a_page(self) -> None:
        labelled = on_page_content(_panzoom_box() + _panzoom_box())

        assert labelled.count('aria-label="Reset zoom"') == 2

    def test_leaves_the_rest_of_the_markup_alone(self) -> None:
        page = _panzoom_box()

        labelled = on_page_content(page)

        assert (
            re.sub(r' aria-(label|hidden)="[^"]*"| focusable="false"', "", labelled)
            == page
        )

    def test_is_idempotent(self) -> None:
        once = on_page_content(_panzoom_box())

        assert on_page_content(once) == once

    def test_keeps_a_name_the_markup_already_has(self) -> None:
        page = (
            '<button class="panzoom-reset panzoom-button" aria-label="Mine"></button>'
        )

        assert on_page_content(page) == page

    def test_ignores_panzoom_markup_shown_as_code(self) -> None:
        page = '<pre><code>&lt;button class="panzoom-reset panzoom-button"&gt;</code></pre>'

        assert on_page_content(page) == page
