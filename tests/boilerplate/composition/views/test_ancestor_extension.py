"""The spec an ancestor's extension file is registered under."""

from pathlib import Path

from boilerplate.composition.views import AncestorExtension


class TestAncestorExtension:
    """The extension's spec names its module and, when it has one, its class."""

    def test_spec_names_the_module_and_class(self) -> None:
        extension = AncestorExtension("core", "1.0.0", Path("x.py"), "pkg.mod", "Ext")

        assert extension.spec == "pkg.mod:Ext"

    def test_spec_is_the_bare_module_without_a_class(self) -> None:
        extension = AncestorExtension("core", "1.0.0", Path("x.py"), "pkg.mod", None)

        assert extension.spec == "pkg.mod"
