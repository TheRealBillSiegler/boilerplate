"""Tests for YAML-safe serialization helpers."""

from __future__ import annotations

from pathlib import Path

import boilerplate
from boilerplate.composition.merging import CopierConfigMerger
from boilerplate.composition.serialization.yaml_utils import (
    extract_complete_copier_config,
    serialize_for_yaml,
)
from boilerplate.integrations.copier_types import Template


class TestExtractCompleteCopierConfig:
    """Extraction covers class-level and init-only Template fields."""

    def test_url_field_is_extracted(self) -> None:
        # Regression: ``url`` is an init-only dataclass field; class-level
        # attribute enumeration dropped ``_url`` from extracted configs.
        template_dir = Path(boilerplate.__file__).parent / "templates" / "project"
        config = extract_complete_copier_config(Template(url=str(template_dir)))
        assert config["_url"] == str(template_dir)

    def test_min_copier_version_is_stringified(self, tmp_path: Path) -> None:
        # Regression: Template.min_copier_version returns a
        # packaging.version.Version, not a str. Leaving it unconverted made
        # serialize_for_yaml raise TypeError (ensure_json rejects Version)
        # before the merger's intersect_versions strategy ever ran.
        (tmp_path / "copier.yml").write_text("_min_copier_version: '1.2.0'\n")

        config = extract_complete_copier_config(Template(url=str(tmp_path)))

        assert config["_min_copier_version"] == "1.2.0"
        assert isinstance(config["_min_copier_version"], str)

    def test_min_copier_version_composes_without_typeerror(
        self, tmp_path: Path
    ) -> None:
        # End-to-end regression for the compose crash: extraction feeds into
        # serialize_for_yaml and then the merger, exercising
        # intersect_versions for real instead of leaving it unreachable.
        base_dir = tmp_path / "base"
        base_dir.mkdir()
        (base_dir / "copier.yml").write_text("_min_copier_version: '1.0.0'\n")
        ext_dir = tmp_path / "ext"
        ext_dir.mkdir()
        (ext_dir / "copier.yml").write_text("_min_copier_version: '1.5.0'\n")

        configs = [
            serialize_for_yaml(extract_complete_copier_config(Template(url=str(d))))
            for d in (base_dir, ext_dir)
        ]

        merged = CopierConfigMerger().merge(configs)

        assert merged["_min_copier_version"] == "1.5.0"
