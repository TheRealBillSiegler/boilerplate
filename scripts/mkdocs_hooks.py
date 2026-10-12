"""MkDocs build hooks for the documentation site.

``mkdocs.yml`` lists this module under ``hooks``, so every build runs it: the
offline bundle's and each ``mike deploy``.

Material for MkDocs copies its search language packs into every build, under
``assets/javascripts/lunr/``. The site's search is English-only, and the
theme's search worker imports a pack only for a language other than English,
so no page ever loads one. ``on_post_build`` deletes the packs, so the site and
the bundle redistribute no file they never use.
"""

import shutil
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
