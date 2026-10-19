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
"""

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
        for line in source.splitlines(keepends=True):
            self._line_starts.append(self._line_starts[-1] + len(line))
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


def on_page_content(html: str, **_kwargs: object) -> str:
    """Name each task-list checkbox by the text of its item.

    Args:
        html: The page's rendered content.
        **_kwargs: The page, config and files MkDocs passes; unused.

    Returns:
        ``html`` with an ``aria-label`` on each task-list checkbox that has
        none. A page without task lists comes back unchanged.
    """
    scanner = _TaskItemScanner(html)
    scanner.feed(html)
    scanner.close()
    # Splice from the end so the earlier offsets stay valid; a nested item
    # closes, and so is recorded, before the item that holds it.
    for offset, text in sorted(scanner.labels, reverse=True):
        label = f' aria-label="{escape(text, quote=True)}"'
        html = html[:offset] + label + html[offset:]
    return html
