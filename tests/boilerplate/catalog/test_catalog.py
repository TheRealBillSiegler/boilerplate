"""Tests for TemplateCatalog registration, resolution, and listing behavior."""

from collections.abc import Callable
from pathlib import Path

import pytest
from packaging.version import InvalidVersion, Version

from boilerplate.catalog import TemplateCatalog
from boilerplate.models.template_info import TemplateInfo

TemplateFactory = Callable[..., TemplateInfo]


class TestRegistration:
    """Registering templates indexes them by tag with a first-one-wins policy."""

    def test_first_registration_wins_for_duplicate_tag(
        self, template_factory: TemplateFactory, tmp_path: Path
    ) -> None:
        first = template_factory("demo", "1.0.0", location=tmp_path / "first")
        second = template_factory("demo", "1.0.0", location=tmp_path / "second")
        catalog = TemplateCatalog()

        catalog.register(first)
        catalog.register(second)

        assert catalog.get_by_tag("demo@1.0.0") is first
        assert len(catalog) == 1

    def test_register_indexes_by_tag_and_by_name_version(
        self, template_factory: TemplateFactory
    ) -> None:
        template = template_factory("demo", "1.0.0")
        catalog = TemplateCatalog()

        catalog.register(template)

        assert catalog.get_by_tag("demo@1.0.0") is template
        assert catalog.resolve("demo", "1.0.0") is template

    def test_register_many_equals_repeated_register(
        self, template_factory: TemplateFactory
    ) -> None:
        templates = [
            template_factory("alpha", "1.0.0"),
            template_factory("beta", "2.0.0"),
        ]
        batch_catalog = TemplateCatalog()
        loop_catalog = TemplateCatalog()

        batch_catalog.register_many(templates)
        for template in templates:
            loop_catalog.register(template)

        assert batch_catalog.list_tags() == loop_catalog.list_tags()
        assert batch_catalog.list_all() == loop_catalog.list_all()

    def test_register_many_duplicates_within_batch_first_wins(
        self, template_factory: TemplateFactory, tmp_path: Path
    ) -> None:
        first = template_factory("demo", "1.0.0", location=tmp_path / "first")
        second = template_factory("demo", "1.0.0", location=tmp_path / "second")
        catalog = TemplateCatalog()

        catalog.register_many([first, second])

        assert catalog.get_by_tag("demo@1.0.0") is first
        assert len(catalog) == 1


class TestResolve:
    """Resolving finds templates by name and optional version."""

    def test_get_by_tag_miss_returns_none(self) -> None:
        assert TemplateCatalog().get_by_tag("missing@1.0.0") is None

    def test_resolve_unknown_name_returns_none(self) -> None:
        assert TemplateCatalog().resolve("missing") is None

    def test_resolve_known_name_absent_version_returns_none(
        self, template_factory: TemplateFactory
    ) -> None:
        catalog = TemplateCatalog()
        catalog.register(template_factory("demo", "1.0.0"))

        assert catalog.resolve("demo", "9.9.9") is None

    def test_resolve_without_version_returns_pep440_latest(
        self, template_factory: TemplateFactory
    ) -> None:
        catalog = TemplateCatalog()
        catalog.register(template_factory("demo", "1.9.0"))
        catalog.register(template_factory("demo", "1.10.0"))

        resolved = catalog.resolve("demo", None)

        assert resolved is not None
        assert resolved.meta.version == Version("1.10.0")

    @pytest.mark.parametrize(
        "versions,expected_latest",
        [
            # A release outranks its own prerelease
            (["2.0.0rc1", "2.0.0"], "2.0.0"),
            # A newer prerelease outranks an older release
            (["1.0.0", "2.0.0rc1"], "2.0.0rc1"),
        ],
    )
    def test_resolve_latest_prerelease_ordering(
        self,
        template_factory: TemplateFactory,
        versions: list[str],
        expected_latest: str,
    ) -> None:
        catalog = TemplateCatalog()
        for version in versions:
            catalog.register(template_factory("demo", version))

        resolved = catalog.resolve("demo", None)

        assert resolved is not None
        assert resolved.meta.version == Version(expected_latest)

    def test_resolve_accepts_version_object_and_string(
        self, template_factory: TemplateFactory
    ) -> None:
        template = template_factory("demo", "1.2.3")
        catalog = TemplateCatalog()
        catalog.register(template)

        assert catalog.resolve("demo", Version("1.2.3")) is template
        assert catalog.resolve("demo", "1.2.3") is template

    def test_resolve_invalid_version_string_raises(
        self, template_factory: TemplateFactory
    ) -> None:
        catalog = TemplateCatalog()
        catalog.register(template_factory("demo", "1.0.0"))

        with pytest.raises(InvalidVersion):
            catalog.resolve("demo", "not-a-version")

    def test_resolve_latest_equals_resolve_with_none(
        self, template_factory: TemplateFactory
    ) -> None:
        catalog = TemplateCatalog()
        catalog.register(template_factory("demo", "1.9.0"))
        catalog.register(template_factory("demo", "1.10.0"))

        assert catalog.resolve_latest("demo") is catalog.resolve("demo", None)


class TestListing:
    """Listing, length, and iteration reflect unique tags in insertion order."""

    def test_list_tags_insertion_order_excludes_duplicates(
        self, template_factory: TemplateFactory, tmp_path: Path
    ) -> None:
        catalog = TemplateCatalog()
        catalog.register(template_factory("beta", "2.0.0"))
        catalog.register(template_factory("alpha", "1.0.0"))
        catalog.register(template_factory("beta", "2.0.0", location=tmp_path / "dup"))

        assert catalog.list_tags() == ["beta@2.0.0", "alpha@1.0.0"]

    def test_list_all_aligns_with_list_tags(
        self, template_factory: TemplateFactory
    ) -> None:
        catalog = TemplateCatalog()
        catalog.register(template_factory("beta", "2.0.0"))
        catalog.register(template_factory("alpha", "1.0.0"))

        tags = catalog.list_tags()
        templates = catalog.list_all()

        assert len(tags) == len(templates)
        for tag, template in zip(tags, templates, strict=True):
            assert tag == f"{template.name}@{template.meta.version}"

    def test_len_counts_unique_tags(
        self, template_factory: TemplateFactory, tmp_path: Path
    ) -> None:
        catalog = TemplateCatalog()
        catalog.register(template_factory("alpha", "1.0.0"))
        catalog.register(template_factory("alpha", "2.0.0"))
        catalog.register(template_factory("alpha", "1.0.0", location=tmp_path / "dup"))

        assert len(catalog) == 2

    def test_len_of_empty_catalog_is_zero(self) -> None:
        assert len(TemplateCatalog()) == 0

    def test_iter_yields_templates_in_insertion_order(
        self, template_factory: TemplateFactory
    ) -> None:
        catalog = TemplateCatalog()
        beta = template_factory("beta", "2.0.0")
        alpha = template_factory("alpha", "1.0.0")
        catalog.register(beta)
        catalog.register(alpha)

        assert list(catalog) == [beta, alpha]
