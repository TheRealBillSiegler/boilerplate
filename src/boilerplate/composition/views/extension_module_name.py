"""Name the module an ancestor's extension file is registered under."""

import hashlib
import re

MODULE_ROOT = "boilerplate_layer_ext"


def extension_module_name(layer: str, release: str, file: str) -> str:
    """Return the module name for `file` of `layer` at `release`.

    The name is a dotted path of identifiers, readable in a traceback, with a
    digest of the exact triple so spellings that sanitize alike ("1.0" and
    "1_0") never collide. Two releases of one file get two names, so the old
    copy and the new copy of an update load their own code in one process.

    Args:
        layer: The ancestor that declares the file.
        release: The ancestor's version.
        file: The file's path inside the layer, POSIX-separated.

    Returns:
        The module name.

    Examples:
        >>> name = extension_module_name("docs", "1.0.0", "_extensions/docfilters.py")
        >>> name.startswith("boilerplate_layer_ext.docs_1_0_0_")
        True
        >>> name.endswith(".docfilters")
        True
    """
    digest = hashlib.sha256("\0".join((layer, release, file)).encode()).hexdigest()
    readable = re.sub(r"\W", "_", f"{layer}_{release}")
    stem = re.sub(r"\W", "_", file.rsplit("/", 1)[-1].removesuffix(".py"))
    return f"{MODULE_ROOT}.{readable}_{digest[:12]}.{stem}"
