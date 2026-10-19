"""MkDocs build hooks for the documentation site.

``mkdocs.yml`` lists this module under ``hooks``, so every build runs it: the
offline bundle's and each ``mike deploy``.

Material for MkDocs copies its search language packs into every build, under
``assets/javascripts/lunr/``. The site's search is English-only, and the
theme's search worker imports a pack only for a language other than English,
so no page ever loads one. ``on_post_build`` deletes the packs, so the site and
the bundle redistribute no file they never use.

The task lists (``pymdownx.tasklist``) render each checkbox inside a ``<label>``
that wraps the box and an empty indicator, with the item's text outside it, so
a screen reader meets a checkbox with no name. ``on_page_content`` gives each
checkbox an ``aria-label`` holding the text of its own item.

Material for MkDocs and mkdocs-panzoom-plugin ship some controls without an
accessible name, and Material takes critical fixes only, so this module names
them at build time. A site that moves to Zensical must port this: Zensical does
not run MkDocs hooks.

- The diagram controls that mkdocs-panzoom-plugin renders (a ``<nav>`` of
  icon-only ``<button>`` elements) get a label on the ``<nav>`` and on each
  button, and their SVG icons are hidden from assistive technology.
  ``on_page_content`` does this, because the plugin writes the markup while the
  page's Markdown renders.
- The theme's search dialog gets an ``aria-label``. ``on_post_page`` does this,
  because the dialog lives in the theme's page template, not the page content.
"""

import re
import shutil
from html import escape
from html.parser import HTMLParser
from pathlib import Path

from mkdocs.config.defaults import MkDocsConfig
from mkdocs.plugins import get_plugin_logger

# MkDocs prints only its own loggers; get_plugin_logger is its documented way
# for a plugin or hook to log under that namespace.
logger = get_plugin_logger(__name__)

SEARCH_LANGUAGE_PACKS = Path("assets", "javascripts", "lunr")


def on_post_build(*, config: MkDocsConfig) -> None:
    """Delete the theme's search language packs from the built site.

    Args:
        config: The build configuration; its ``site_dir`` holds the built site.
    """
    packs = Path(config.site_dir) / SEARCH_LANGUAGE_PACKS
    if packs.is_dir():
        shutil.rmtree(packs)
        logger.info("Dropped the unused search language packs at %s", packs)


_TASK_ITEM_CLASS = "task-list-item"
_LIST_TAGS = frozenset({"ul", "ol"})
_INPUT_TAG_LENGTH = len("<input")


class _TaskItemScanner(HTMLParser):
    """Find each unlabelled task-list checkbox and the text of its own item.

    A task item is an ``<li class="task-list-item">``. Its own text is the text
    of the item up to a nested list, so a parent item is not named by its
    children. Inline markup (``<code>``, ``<a>``) contributes its text.

    Attributes:
        labels: ``(offset, text)`` pairs, one per unlabelled checkbox found:
            the offset in the scanned source just after ``<input``, and the
            whitespace-collapsed text of the item that holds it.
    """

    def __init__(self, source: str) -> None:
        """Prepare to scan ``source``.

        Args:
            source: The HTML to scan; offsets in ``labels`` index into it.
        """
        super().__init__(convert_charrefs=True)
        self.labels: list[tuple[int, str]] = []
        self._line_starts = [0]
        # Split on "\n" alone: HTMLParser.getpos() counts lines that way, and
        # str.splitlines() also breaks at form feeds and U+2028.
        for line in source.split("\n")[:-1]:
            self._line_starts.append(self._line_starts[-1] + len(line) + 1)
        # One entry per open <li>: its index among the task items, or None.
        self._open_items: list[int | None] = []
        self._insert_at: list[int | None] = []
        self._texts: list[list[str]] = []
        self._collecting: list[bool] = []

    def _innermost_task_item(self) -> int | None:
        return self._open_items[-1] if self._open_items else None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Track open items and note each unlabelled checkbox.

        Args:
            tag: The start tag's name.
            attrs: The tag's attributes.
        """
        attributes = dict(attrs)
        item = self._innermost_task_item()
        if tag == "li":
            classes = (attributes.get("class") or "").split()
            if _TASK_ITEM_CLASS in classes:
                self._open_items.append(len(self._insert_at))
                self._insert_at.append(None)
                self._texts.append([])
                self._collecting.append(True)
            else:
                self._open_items.append(None)
        elif tag in _LIST_TAGS and item is not None:
            self._collecting[item] = False
        elif (
            tag == "input"
            and attributes.get("type") == "checkbox"
            and "aria-label" not in attributes
            and item is not None
            and self._insert_at[item] is None
        ):
            line, column = self.getpos()
            self._insert_at[item] = (
                self._line_starts[line - 1] + column + _INPUT_TAG_LENGTH
            )

    def handle_endtag(self, tag: str) -> None:
        """Close an item and record its checkbox with the item's text.

        Args:
            tag: The end tag's name.
        """
        if tag != "li" or not self._open_items:
            return
        item = self._open_items.pop()
        if item is None:
            return
        offset = self._insert_at[item]
        text = " ".join("".join(self._texts[item]).split())
        if offset is not None and text:
            self.labels.append((offset, text))

    def handle_data(self, data: str) -> None:
        """Add text to the innermost task item while it still collects.

        Args:
            data: A run of text, character references already decoded.
        """
        item = self._innermost_task_item()
        if item is not None and self._collecting[item]:
            self._texts[item].append(data)


_PANZOOM_BUTTON_NAMES = {
    "panzoom-info": "Show pan and zoom help",
    "panzoom-reset": "Reset zoom",
    "panzoom-max": "Enter full screen",
    "panzoom-min": "Exit full screen",
}
_PANZOOM_NAV_NAME = "Diagram controls"
_PANZOOM_START_TAG = re.compile(
    r'<(?P<tag>button|svg|nav) class="(?P<classes>panzoom-[^"]*)"[^>]*>'
)


def _name_panzoom_start_tag(match: re.Match[str]) -> str:
    """Return a panzoom start tag with its accessible name or icon hiding added."""
    start_tag = match.group(0)
    tag = match.group("tag")
    first_class = match.group("classes").split()[0]
    attributes = ""
    if tag == "svg" and "aria-hidden" not in start_tag:
        attributes = ' aria-hidden="true" focusable="false"'
    elif tag == "button" and "aria-label" not in start_tag:
        name = _PANZOOM_BUTTON_NAMES.get(first_class)
        attributes = f' aria-label="{name}"' if name else ""
    elif (
        tag == "nav" and first_class == "panzoom-nav" and "aria-label" not in start_tag
    ):
        attributes = f' aria-label="{_PANZOOM_NAV_NAME}"'
    return start_tag[:-1] + attributes + ">"


def on_page_content(html: str, **_kwargs: object) -> str:
    """Name each task-list checkbox and each diagram control.

    Args:
        html: The page's rendered content.
        **_kwargs: The page, config and files MkDocs passes; unused.

    Returns:
        ``html`` with an ``aria-label`` on each task-list checkbox that has
        none, an ``aria-label`` on each panzoom ``<nav>`` and button that has
        none, and ``aria-hidden`` on each panzoom icon. A page with neither
        task lists nor diagrams comes back unchanged.
    """
    html = _PANZOOM_START_TAG.sub(_name_panzoom_start_tag, html)
    scanner = _TaskItemScanner(html)
    scanner.feed(html)
    scanner.close()
    # Splice from the end so the earlier offsets stay valid; a nested item
    # closes, and so is recorded, before the item that holds it.
    for offset, text in sorted(scanner.labels, reverse=True):
        label = f' aria-label="{escape(text, quote=True)}"'
        html = html[:offset] + label + html[offset:]
    return html


_SEARCH_DIALOG = re.compile(
    r'<div\b(?=[^>]*\bdata-md-component="search")(?=[^>]*\brole="dialog")'
    r"(?![^>]*\baria-label=)[^>]*>"
)


def on_post_page(output: str, **_kwargs: object) -> str:
    """Name the theme's search dialog.

    Args:
        output: The page's complete HTML, theme template included.
        **_kwargs: The page and config MkDocs passes; unused.

    Returns:
        ``output`` with ``aria-label="Search"`` on the search dialog if it has
        no label. A page without the dialog comes back unchanged.
    """
    return _SEARCH_DIALOG.sub(
        lambda m: m.group(0)[:-1] + ' aria-label="Search">', output
    )
