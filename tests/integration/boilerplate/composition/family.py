"""Build the made-up template family into tagged git repositories.

The family is five small Python-project templates (`core`, `service`, `docs`,
`ci`, `app`) stored as data under ``tests/fixtures/family/<layer>/<version>/``.
A layer's first version is a full template folder; each later version holds only
the files it adds or changes, plus a ``_deleted.txt`` naming the paths it
removes. ``build_family`` overlays each version on the previous one and turns
the result into a git repository with one commit and one tag per release.
"""

import importlib.util
import shutil
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import NamedTuple

import pytest
from packaging.version import Version

from tests.boilerplate.templates.conftest import build_layer_repo, copy_layer_into

FAMILY_DATA = Path(__file__).parents[3] / "fixtures" / "family"
DELETED_LIST = "_deleted.txt"


class Family(NamedTuple):
    """The built family.

    Attributes:
        repos: Each layer's git repository, tagged at every release.
        tags: Each layer's tags, oldest release first.
        releases: Each layer's full template folder at each tag, keyed by layer
            and then tag.
    """

    repos: dict[str, Path]
    tags: dict[str, list[str]]
    releases: dict[str, dict[str, Path]]


def family_versions() -> dict[str, list[str]]:
    """Return each layer's release versions from the stored data, oldest first."""
    return {
        layer.name: sorted((v.name for v in layer.iterdir()), key=Version)
        for layer in sorted(FAMILY_DATA.iterdir())
        if layer.is_dir()
    }


def _remove_listed_paths(release: Path) -> None:
    """Delete the paths `release`'s ``_deleted.txt`` lists, then the list itself."""
    listing = release / DELETED_LIST
    if not listing.exists():
        return
    for relative in listing.read_text(encoding="utf-8").splitlines():
        target = release / relative
        target.unlink()
        for parent in target.relative_to(release).parents[:-1]:
            if not any((release / parent).iterdir()):
                (release / parent).rmdir()
    listing.unlink()


def _overlay_releases(layer: str, versions: list[str], root: Path) -> dict[str, Path]:
    """Materialize `layer`'s full template folder at each version under `root`."""
    releases: dict[str, Path] = {}
    previous: Path | None = None
    for version in versions:
        release = root / layer / version
        if previous is not None:
            copy_layer_into(previous, release)
        copy_layer_into(FAMILY_DATA / layer / version, release)
        _remove_listed_paths(release)
        releases[version] = release
        previous = release
    return releases


def build_family(root: Path) -> Family:
    """Build every layer of the family into a tagged git repository.

    Args:
        root: A directory to build under; it holds ``releases/`` (each layer's
            full folder per version) and ``repos/`` (each layer's repository).

    Returns:
        The repositories, their tags and the full folder at each tag.
    """
    versions = family_versions()
    releases = {
        layer: _overlay_releases(layer, tags, root / "releases")
        for layer, tags in versions.items()
    }
    repos = {
        layer: build_layer_repo(root / "repos" / layer, layer_releases)
        for layer, layer_releases in releases.items()
    }
    return Family(repos, versions, releases)


def assemble_templates_dir(
    family: Family, dest: Path, versions: Mapping[str, str]
) -> Path:
    """Copy the chosen release of each layer into one templates directory.

    A composition resolves its layers by name from a directory holding one
    folder per layer, so a scenario picks a tag for every layer it needs.

    Args:
        family: The built family.
        dest: The directory to create.
        versions: The tag to copy for each layer, keyed by layer name.

    Returns:
        The templates directory.
    """
    for layer, tag in versions.items():
        shutil.copytree(
            family.releases[layer][tag],
            dest / layer,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    return dest


def register_extension_module(patch: pytest.MonkeyPatch, path: Path, name: str) -> str:
    """Import the extension file at `path` as module `name`, undone with `patch`.

    A descendant cannot name an ancestor's file-path extension spec, but it can
    load the same file as an importable module the composition adds to its
    render.

    Args:
        patch: The patch context that removes the module again.
        path: The extension file.
        name: The dotted module name to register it under.

    Returns:
        `name`, for building a ``name:Class`` extension spec.
    """
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    patch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return name
