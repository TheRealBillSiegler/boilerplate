"""``grants_unsafe`` decides whether a layer's Worker loads a Jinja extension.

Copier refuses to load an extension without its ``unsafe`` grant, and
docs/design/adr-003-permissive-execution.md grants it only where an extension
or a task needs it, so a layer that loads none keeps Copier's consent gate.
"""

from pathlib import Path

import pytest

from boilerplate.composition.models.composition_layer import CompositionLayer
from boilerplate.composition.rendering.grants_unsafe import grants_unsafe
from boilerplate.composition.views import AncestorExtension, LayerView

_ANCESTOR_FILE = AncestorExtension(
    layer="core",
    release="1.0.0",
    path=Path("_extensions/context.py"),
    module="boilerplate_ext_core_1_0_0_context",
    class_name="ContextUpdater",
)


def _layer(**values: object) -> CompositionLayer:
    return CompositionLayer(
        name="demo",
        version="1.0.0",
        path=Path("demo"),
        values=values,  # pyright: ignore[reportArgumentType]
    )


class TestGrantsUnsafe:
    @pytest.mark.parametrize(
        "values",
        [{}, {"_jinja_extensions": []}],
        ids=["no_declaration", "empty_declaration"],
    )
    def test_a_layer_that_loads_no_extension_keeps_the_consent_gate(
        self, values: dict[str, object]
    ) -> None:
        assert grants_unsafe(_layer(**values), LayerView({}, ())) is False

    def test_an_importable_extension_in_the_view_is_granted(self) -> None:
        view = LayerView({}, ("probe_ext.ProbeExtension",))

        assert grants_unsafe(_layer(), view) is True

    def test_an_ancestors_extension_file_in_the_view_is_granted(self) -> None:
        view = LayerView({}, (), (_ANCESTOR_FILE,))

        assert grants_unsafe(_layer(), view) is True

    def test_an_extension_only_the_layer_itself_declares_is_granted(self) -> None:
        """A filepath-style spec never reaches the view; Copier still loads it."""
        layer = _layer(_jinja_extensions=["_extensions/context.py:ContextUpdater"])

        assert grants_unsafe(layer, LayerView({}, ())) is True
