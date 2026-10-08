"""The view a composition gives the layer it is rooted at.

The expected questions and extensions are read off the composition's merged
schema (design 04, per-layer render loop): questions are the schema's
non-directive keys; extensions are its importable ``_jinja_extensions``.
"""

from collections.abc import Callable
from typing import Any

import pytest

from boilerplate.composition.models import Composition
from boilerplate.composition.views import (
    LayerView,
    build_layer_view,
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
