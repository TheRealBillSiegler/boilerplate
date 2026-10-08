"""Register ancestors' extension files as importable modules for one render."""

import importlib.util
import sys
from collections.abc import Generator, Iterable
from contextlib import contextmanager

from boilerplate.composition.views.ancestor_extension import AncestorExtension


@contextmanager
def registered_ancestor_extensions(
    extensions: Iterable[AncestorExtension],
) -> Generator[None]:
    """Register each extension file as a module for the duration of the block.

    Copier imports a ``module:Class`` extension spec when it builds the render's
    Jinja environment, so the modules must be importable while the render runs.
    A module already registered, by an enclosing block, is left alone and stays
    when this block ends. When one file fails to load, the block's earlier
    registrations are undone before the error propagates.

    Args:
        extensions: The files to register, each under its own module name.

    Yields:
        Nothing; the modules are importable inside the block.

    Raises:
        ImportError: If a file cannot be loaded as a module.
    """
    added: list[str] = []
    try:
        for extension in extensions:
            if extension.module in sys.modules:
                continue
            spec = importlib.util.spec_from_file_location(
                extension.module, extension.path
            )
            if spec is None or spec.loader is None:
                raise ImportError(f"cannot load extension file {extension.path}")
            module = importlib.util.module_from_spec(spec)
            sys.modules[extension.module] = module
            added.append(extension.module)
            spec.loader.exec_module(module)
        yield
    finally:
        for name in added:
            sys.modules.pop(name, None)
