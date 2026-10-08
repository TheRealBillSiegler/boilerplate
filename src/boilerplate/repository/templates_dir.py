"""Gather release checkouts into one templates directory."""

import shutil
from collections.abc import Mapping
from pathlib import Path


def assemble_templates_dir(layers: Mapping[str, Path], dest: Path) -> Path:
    """Copy each layer's checkout into `dest` under the layer's name.

    The catalog discovers templates by scanning a directory, one folder per
    layer, so a composition at a chosen set of releases is a directory that holds
    exactly those releases. Git history and bytecode caches stay behind: a copy
    with a ``.git`` folder would read as a git-backed source, and Copier would
    clone it again at its latest tag.

    Args:
        layers: Each layer's checkout, keyed by layer name.
        dest: The directory to fill; created with its parents when missing.

    Returns:
        `dest`.
    """
    for name, checkout in layers.items():
        shutil.copytree(
            checkout,
            dest / name,
            ignore=shutil.ignore_patterns(".git", "__pycache__"),
        )
    return dest
