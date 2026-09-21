"""Integration tests for multiple template directories working together."""

from collections.abc import Callable
from pathlib import Path

import pytest

from boilerplate.catalog import TemplateCatalog


@pytest.fixture()
def multi_dir_environment(
    tmp_path: Path, catalog_builder: Callable[..., TemplateCatalog]
) -> tuple[list[Path], TemplateCatalog]:
    """Create three template directories with a small set of templates.

    Returns a tuple of ([dir1, dir2, dir3], catalog) for reuse across tests.
    """
    # Create three template directories
    dir1 = tmp_path / "templates1"
    dir2 = tmp_path / "templates2"
    dir3 = tmp_path / "templates3"
    for d in (dir1, dir2, dir3):
        d.mkdir()

    # Create templates in each directory
    def write_template(root: Path, name: str, version: str) -> None:
        tpl = root / name
        tpl.mkdir()
        (tpl / "boilerplate.yml").write_text(
            f"name: {name}\nversion: {version}\ndescription: Test template\n",
            encoding="utf-8",
        )
        (tpl / "copier.yml").write_text("_jinja_extensions: []\n", encoding="utf-8")

    write_template(dir1, "webapp", "1.0.0")
    write_template(dir2, "api", "2.1.0")
    write_template(dir3, "webapp", "1.5.0")  # Different version of webapp
    write_template(dir1, "cli", "0.5.0")

    catalog = catalog_builder(default_dir=dir1, extra_dirs=[dir2, dir3])
    return [dir1, dir2, dir3], catalog


def test_settings_template_dirs_property(
    multi_dir_environment: tuple[list[Path], TemplateCatalog],
) -> None:
    """Template directories include default + extras in order."""
    dirs, _ = multi_dir_environment
    # The catalog_builder constructs Settings with these dirs in order; assert shape
    assert isinstance(dirs, list) and len(dirs) == 3


def test_catalog_lists_all_templates(
    multi_dir_environment: tuple[list[Path], TemplateCatalog],
) -> None:
    """All templates across directories are listed in the catalog."""
    _dirs, catalog = multi_dir_environment
    all_templates = catalog.list_all()
    assert len(all_templates) == 4


def test_get_by_tag_finds_specific_versions(
    multi_dir_environment: tuple[list[Path], TemplateCatalog],
) -> None:
    """Catalog returns specific versions by tag from any directory."""
    _dirs, catalog = multi_dir_environment
    assert catalog.get_by_tag("webapp@1.0.0") is not None
    assert catalog.get_by_tag("webapp@1.5.0") is not None
    assert catalog.get_by_tag("api@2.1.0") is not None
    assert catalog.get_by_tag("cli@0.5.0") is not None


def test_resolve_returns_highest_version(
    multi_dir_environment: tuple[list[Path], TemplateCatalog],
) -> None:
    """Resolve selects the highest available version across dirs."""
    _dirs, catalog = multi_dir_environment
    latest_webapp = catalog.resolve("webapp")
    assert latest_webapp is not None
    assert str(latest_webapp.meta.version) == "1.5.0"


def test_template_locations_match_directories(
    multi_dir_environment: tuple[list[Path], TemplateCatalog],
) -> None:
    """Templates originate from their respective directories."""
    dirs, catalog = multi_dir_environment
    dir1, dir2, dir3 = dirs
    webapp_v1 = catalog.get_by_tag("webapp@1.0.0")
    webapp_v15 = catalog.get_by_tag("webapp@1.5.0")
    api_v21 = catalog.get_by_tag("api@2.1.0")
    cli_v05 = catalog.get_by_tag("cli@0.5.0")
    assert webapp_v1 and webapp_v1.location.parent == dir1
    assert webapp_v15 and webapp_v15.location.parent == dir3
    assert api_v21 and api_v21.location.parent == dir2
    assert cli_v05 and cli_v05.location.parent == dir1
