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
    build_step_view,
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

    def test_secret_questions_accumulate_across_the_layers(
        self, composition_factory: Callable[..., Composition]
    ) -> None:
        """Design 04: the scoped view holds the accumulated `_secret_questions`."""
        composition = composition_factory(
            ["base@1.0.0", "child@1.0.0"],
            [
                {"token": {}, "_secret_questions": ["token"]},
                {"key": {}, "_secret_questions": ["key"]},
            ],
            {},
        )

        assert build_layer_view(composition).secret_questions == {"token", "key"}


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


class TestDeclaredBy:
    """The view names the layer that declares each of its questions."""

    def test_the_first_layer_to_hold_a_question_declares_it(
        self, composition_factory: Callable[..., Composition]
    ) -> None:
        composition = composition_factory(
            ["base@1.0.0", "child@1.0.0"],
            [{"a": {"type": "str"}}, {"b": {"type": "str"}}],
            {},
        )

        assert dict(build_layer_view(composition).declared_by) == {
            "a": "base",
            "b": "child",
        }

    def test_a_later_layers_override_does_not_declare_the_question(
        self, composition_factory: Callable[..., Composition]
    ) -> None:
        composition = composition_factory(
            ["base@1.0.0", "child@1.0.0"],
            [{"a": {"type": "str", "default": "x"}}, {"a": {"default": "y"}}],
            {},
        )

        assert dict(build_layer_view(composition).declared_by) == {"a": "base"}

    def test_directives_are_not_questions(
        self, composition_factory: Callable[..., Composition]
    ) -> None:
        composition = composition_factory(
            ["base@1.0.0"], [{"_answers_file": "x", "a": {}}], {}
        )

        assert dict(build_layer_view(composition).declared_by) == {"a": "base"}


class TestBuildStepView:
    """A step's view takes definitions from the full schema, names from the scope."""

    def _views(
        self, composition_factory: Callable[..., Composition]
    ) -> tuple[Composition, Composition]:
        scoped = composition_factory(
            ["base@1.0.0"], [{"a": {"type": "str", "default": "base"}}], {}
        )
        full = composition_factory(
            ["base@1.0.0", "child@1.0.0"],
            [
                {"a": {"type": "str", "default": "base"}},
                {"a": {"default": "child"}, "b": {"type": "str"}},
            ],
            {},
        )
        return scoped, full

    def test_a_descendants_override_sets_the_definition(
        self, composition_factory: Callable[..., Composition]
    ) -> None:
        scoped, full = self._views(composition_factory)

        assert build_step_view(scoped, full).questions["a"]["default"] == "child"

    def test_the_questions_follow_the_scope(
        self, composition_factory: Callable[..., Composition]
    ) -> None:
        scoped, full = self._views(composition_factory)

        assert list(build_step_view(scoped, full).questions) == ["a"]

    def test_declaring_layers_follow_the_scope_not_the_full_schema(
        self, composition_factory: Callable[..., Composition]
    ) -> None:
        """A sibling that declares the question first in the full schema is no owner."""
        scoped = composition_factory(
            ["base@1.0.0", "child@1.0.0"],
            [{}, {"foo": {"type": "str"}}],
            {},
        )
        full = composition_factory(
            ["base@1.0.0", "sibling@1.0.0", "child@1.0.0"],
            [{}, {"foo": {"type": "str"}}, {"foo": {"default": "x"}}],
            {},
        )

        assert dict(build_step_view(scoped, full).declared_by) == {"foo": "child"}

    def test_extensions_come_from_the_scope(
        self, composition_factory: Callable[..., Composition]
    ) -> None:
        scoped = composition_factory(
            ["base@1.0.0"], [{"_jinja_extensions": ["a.mod"]}], {}
        )
        full = composition_factory(
            ["base@1.0.0", "child@1.0.0"],
            [{"_jinja_extensions": ["a.mod"]}, {"_jinja_extensions": ["b.mod"]}],
            {},
        )

        assert build_step_view(scoped, full).extensions == ("a.mod",)
