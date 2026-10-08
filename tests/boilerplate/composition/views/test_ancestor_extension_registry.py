"""Registering ancestors' extension files as importable modules for one render."""

import importlib
import sys
from pathlib import Path

import pytest

from boilerplate.composition.views import (
    AncestorExtension,
    registered_ancestor_extensions,
)


def _extension(tmp_path: Path, release: str, body: str) -> AncestorExtension:
    path = tmp_path / release / "ext.py"
    path.parent.mkdir(parents=True)
    path.write_text(body, encoding="utf-8")
    return AncestorExtension(
        layer="docs",
        release=release,
        path=path,
        module=f"registry_probe.docs_{release}.ext",
        class_name="Ext",
    )


class TestRegisteredAncestorExtensions:
    def test_the_module_imports_inside_the_block(self, tmp_path: Path) -> None:
        extension = _extension(tmp_path, "1", "VALUE = 'one'\n")

        with registered_ancestor_extensions([extension]):
            module = importlib.import_module(extension.module)

        assert module.VALUE == "one"

    def test_the_module_is_gone_after_the_block(self, tmp_path: Path) -> None:
        extension = _extension(tmp_path, "1", "VALUE = 'one'\n")

        with registered_ancestor_extensions([extension]):
            pass

        assert extension.module not in sys.modules

    def test_the_module_is_gone_after_the_block_raises(self, tmp_path: Path) -> None:
        extension = _extension(tmp_path, "1", "VALUE = 'one'\n")

        with pytest.raises(RuntimeError), registered_ancestor_extensions([extension]):
            raise RuntimeError("render failed")

        assert extension.module not in sys.modules

    def test_a_module_that_fails_to_load_leaves_none_of_the_block_behind(
        self, tmp_path: Path
    ) -> None:
        good = _extension(tmp_path, "1", "VALUE = 'one'\n")
        bad = _extension(tmp_path, "2", "raise RuntimeError('broken')\n")

        with (
            pytest.raises(RuntimeError, match="broken"),
            registered_ancestor_extensions([good, bad]),
        ):
            pass

        assert (good.module in sys.modules, bad.module in sys.modules) == (False, False)

    def test_two_releases_of_one_file_load_their_own_code_side_by_side(
        self, tmp_path: Path
    ) -> None:
        old = _extension(tmp_path, "1", "VALUE = 'one'\n")
        new = _extension(tmp_path, "2", "VALUE = 'two'\n")

        with registered_ancestor_extensions([old, new]):
            values = (
                importlib.import_module(old.module).VALUE,
                importlib.import_module(new.module).VALUE,
            )

        assert values == ("one", "two")

    def test_a_module_an_outer_block_registered_survives_an_inner_one(
        self, tmp_path: Path
    ) -> None:
        extension = _extension(tmp_path, "1", "VALUE = 'one'\n")

        with registered_ancestor_extensions([extension]):
            with registered_ancestor_extensions([extension]):
                pass
            still_registered = extension.module in sys.modules

        assert still_registered
