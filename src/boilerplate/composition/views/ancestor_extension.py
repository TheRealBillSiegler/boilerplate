"""An ancestor's file-path extension, recorded for a descendant's render."""

from pathlib import Path
from typing import NamedTuple


class AncestorExtension(NamedTuple):
    """A file-path ``_jinja_extensions`` spec an ancestor declares.

    A file-path spec resolves inside the template that declares it, so a
    descendant cannot name it. The view records the file at the ancestor's
    release instead, under a module name unique to that release, and the render
    registers the file as an importable module under that name.

    Attributes:
        layer: The ancestor that declares the spec.
        release: The ancestor's version the file belongs to.
        path: The extension file at that release.
        module: The module name to register the file under.
        class_name: The extension class the spec names, if any.
    """

    layer: str
    release: str
    path: Path
    module: str
    class_name: str | None

    @property
    def spec(self) -> str:
        """The importable ``module[:Class]`` spec for the registered module."""
        return f"{self.module}:{self.class_name}" if self.class_name else self.module
