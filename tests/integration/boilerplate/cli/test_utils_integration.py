"""Integration tests for boilerplate.cli.utils."""

from pathlib import Path

from boilerplate.cli.utils import build_template_catalog
from boilerplate.composition.resolution import Resolver
from boilerplate.settings import Settings


def test_build_template_catalog_engine_success(fake_template_dir: Path) -> None:
    """Integration test: catalog helper builds a catalog usable by the resolver."""
    settings = Settings()

    registry = build_template_catalog(fake_template_dir, settings)

    # Verify the resolver can resolve dependencies using the built catalog
    resolution = Resolver().resolve("mytpl", registry)
    assert resolution.execution_sequence
    assert len(resolution.execution_sequence) >= 1
    assert resolution.templates


def _write_fixture_template(
    parent: Path, name: str, *, version: str = "1.0.0", extends: list[str] | None = None
) -> Path:
    """Writes a minimal template under ``parent/<name>`` and returns its directory."""
    tpl_dir = parent / name
    tpl_dir.mkdir(parents=True)
    (tpl_dir / "copier.yml").write_text("# empty config\n")
    extends_yaml = extends or []
    (tpl_dir / "boilerplate.yml").write_text(
        f"""
schema_version: "1.0.0"
name: "{name}"
description: "Fixture template."
version: "{version}"
extends: {extends_yaml!r}
"""
    )
    return tpl_dir


def test_build_template_catalog_extends_bundled_template(
    tmp_path: Path, real_templates_dir: Path
) -> None:
    """A --templates-dir template can extend a bundled template.

    Per docs/design/05-cli-reference.md §Global Options, the flag's directory
    is added to the search path, not substituted for it, so the bundled
    `project` template stays resolvable for `extends`.
    """
    third_party_dir = tmp_path / "third_party"
    _write_fixture_template(third_party_dir, "custom", extends=["project"])

    settings = Settings(default_templates_dir=real_templates_dir)
    catalog = build_template_catalog(third_party_dir, settings)

    resolution = Resolver().resolve("custom", catalog)

    resolved_names = {template.name for template in resolution.templates.values()}
    assert resolved_names == {"project", "custom"}


def test_build_template_catalog_keeps_bundled_templates_when_flag_set(
    tmp_path: Path, real_templates_dir: Path
) -> None:
    """Bundled templates stay listed in the catalog when --templates-dir is set."""
    third_party_dir = tmp_path / "third_party"
    _write_fixture_template(third_party_dir, "custom")

    settings = Settings(default_templates_dir=real_templates_dir)
    catalog = build_template_catalog(third_party_dir, settings)

    names = {template.name for template in catalog}
    assert names == {"custom", "project", "streamlit"}


def test_build_template_catalog_flag_dir_wins_on_name_collision(
    tmp_path: Path, real_templates_dir: Path
) -> None:
    """Flag-dir templates win name collisions (first-wins policy).

    Per docs/design/01-overview.md §Precedence policies, catalog registration
    is first-wins; prepending the flag's directory (rather than appending it)
    gives it priority over bundled/configured templates on collision.
    """
    override_dir = tmp_path / "override"
    override_project_dir = _write_fixture_template(
        override_dir, "project", version="0.1.0"
    )

    settings = Settings(default_templates_dir=real_templates_dir)
    catalog = build_template_catalog(override_dir, settings)

    resolved = catalog.resolve("project", "0.1.0")
    assert resolved is not None
    assert resolved.location == override_project_dir
