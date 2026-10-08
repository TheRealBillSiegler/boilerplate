"""The view a composition gives the layer it is rooted at.

The expected questions and extensions are read off the composition's merged
schema (design 04, per-layer render loop): questions are the schema's
non-directive keys; extensions are its importable ``_jinja_extensions``.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from boilerplate.composition.models import Composition
from boilerplate.composition.views import (
    AncestorExtension,
    LayerView,
    build_layer_view,
    extension_module_name,
    is_layer_local_extension,
    view_config,
)

ANCESTOR_SPEC = "pkg.filters:AncestorFilter"
LOCAL_SPEC = "_extensions/context.py:ContextUpdater"


class TestBuildLayerView:
    """The view holds the merged questions and the importable extensions."""

    def test_questions_are_the_merged_non_directive_keys(
        self, composition_factory: Callable[..., Composition]
    ) -> None:
        composition = composition_factory(
            ["core@1.0.0"],
            None,
            {"name": {"type": "str"}, "_tasks": [["echo"]], "_answers_file": "x"},
        )

        assert dict(build_layer_view(composition).questions) == {
            "name": {"type": "str"}
        }

    def test_extensions_keep_importable_specs_in_merge_order(
        self, composition_factory: Callable[..., Composition]
    ) -> None:
        composition = composition_factory(
            ["core@1.0.0"],
            None,
            {"_jinja_extensions": ["b.mod:B", ANCESTOR_SPEC, "a.mod"]},
        )

        assert build_layer_view(composition).extensions == (
            "b.mod:B",
            ANCESTOR_SPEC,
            "a.mod",
        )

    def test_layer_local_file_path_specs_are_excluded(
        self, composition_factory: Callable[..., Composition]
    ) -> None:
        composition = composition_factory(
            ["core@1.0.0"],
            None,
            {"_jinja_extensions": [ANCESTOR_SPEC, LOCAL_SPEC]},
        )

        assert build_layer_view(composition).extensions == (ANCESTOR_SPEC,)

    def test_no_declared_extensions_gives_an_empty_tuple(
        self, composition_factory: Callable[..., Composition]
    ) -> None:
        composition = composition_factory(["core@1.0.0"], None, {"name": {}})

        assert build_layer_view(composition).extensions == ()


class TestAncestorExtensions:
    """The view records each ancestor's file-path extension file at its release."""

    def test_ancestors_file_path_specs_are_recorded_with_their_release_file(
        self, composition_factory: Callable[..., Composition]
    ) -> None:
        composition = composition_factory(
            ["base@1.2.0", "child@1.0.0"],
            [{"_jinja_extensions": [LOCAL_SPEC]}, {}],
            {},
        )
        core = composition.layers[0]

        assert build_layer_view(composition).ancestor_extensions == (
            AncestorExtension(
                layer="base",
                release="1.2.0",
                path=core.path / "_extensions" / "context.py",
                module=extension_module_name("base", "1.2.0", "_extensions/context.py"),
                class_name="ContextUpdater",
            ),
        )

    def test_the_rooted_layers_own_file_path_specs_are_not_recorded(
        self, composition_factory: Callable[..., Composition]
    ) -> None:
        """Leave the final layer's own spec to Copier, which resolves it itself."""
        composition = composition_factory(
            ["base@1.0.0", "child@1.0.0"],
            [{}, {"_jinja_extensions": [LOCAL_SPEC]}],
            {},
        )

        assert build_layer_view(composition).ancestor_extensions == ()

    def test_ancestors_importable_specs_are_not_recorded(
        self, composition_factory: Callable[..., Composition]
    ) -> None:
        composition = composition_factory(
            ["base@1.0.0", "child@1.0.0"],
            [{"_jinja_extensions": [ANCESTOR_SPEC]}, {}],
            {},
        )

        assert build_layer_view(composition).ancestor_extensions == ()

    def test_a_spec_with_no_class_records_no_class_name(
        self, composition_factory: Callable[..., Composition]
    ) -> None:
        composition = composition_factory(
            ["base@1.0.0", "child@1.0.0"],
            [{"_jinja_extensions": ["_extensions/context.py"]}, {}],
            {},
        )

        assert [
            e.class_name for e in build_layer_view(composition).ancestor_extensions
        ] == [None]


class TestAncestorExtension:
    def test_spec_names_the_module_and_class(self) -> None:
        extension = AncestorExtension("core", "1.0.0", Path("x.py"), "pkg.mod", "Ext")

        assert extension.spec == "pkg.mod:Ext"

    def test_spec_is_the_bare_module_without_a_class(self) -> None:
        extension = AncestorExtension("core", "1.0.0", Path("x.py"), "pkg.mod", None)

        assert extension.spec == "pkg.mod"


class TestViewConfig:
    """The config carries the view's extensions, then the extra ones."""

    @pytest.mark.parametrize(
        ("view", "extra", "expected"),
        [
            (LayerView({}, ()), (), {"skip_if_exists": []}),
            (
                LayerView({}, ("a.mod",)),
                ("b.mod",),
                {"skip_if_exists": [], "jinja_extensions": ["a.mod", "b.mod"]},
            ),
            (
                LayerView({}, ()),
                ("b.mod",),
                {"skip_if_exists": [], "jinja_extensions": ["b.mod"]},
            ),
        ],
    )
    def test_extensions_are_view_then_extra(
        self,
        view: LayerView,
        extra: tuple[str, ...],
        expected: dict[str, Any],
    ) -> None:
        assert view_config(view, extra, skip_if_exists=[]) == expected

    def test_ancestor_extensions_sit_between_the_views_and_the_extra(self) -> None:
        view = LayerView(
            {},
            ("a.mod",),
            (AncestorExtension("core", "1.0.0", Path("x.py"), "reg.mod", "Ext"),),
        )

        assert view_config(view, ("b.mod",))["jinja_extensions"] == [
            "a.mod",
            "reg.mod:Ext",
            "b.mod",
        ]


class TestIsLayerLocalExtension:
    @pytest.mark.parametrize(
        ("spec", "expected"),
        [
            (LOCAL_SPEC, True),
            ("../shared/ext.py:Ext", True),
            ("pkg.module.slugify:SlugifyExtension", False),
            ("pkg.module", False),
        ],
    )
    def test_only_dotted_import_paths_are_shareable(
        self, spec: str, expected: bool
    ) -> None:
        assert is_layer_local_extension(spec) is expected
