"""``LayerView.loads_extensions`` says whether a render under the view loads one."""

from pathlib import Path

import pytest

from boilerplate.composition.views import AncestorExtension, LayerView

_ANCESTOR_FILE = AncestorExtension(
    layer="core",
    release="1.0.0",
    path=Path("_extensions/context.py"),
    module="boilerplate_ext_core_1_0_0_context",
    class_name="ContextUpdater",
)


class TestLoadsExtensions:
    @pytest.mark.parametrize(
        ("view", "expected"),
        [
            (LayerView({}, ()), False),
            (LayerView({}, ("probe_ext.ProbeExtension",)), True),
            (LayerView({}, (), (_ANCESTOR_FILE,)), True),
        ],
        ids=["none", "importable", "ancestor_file"],
    )
    def test_follows_the_extensions_the_view_holds(
        self, view: LayerView, expected: bool
    ) -> None:
        assert view.loads_extensions is expected
