"""A layer rendered from a plain template folder, which records no commit."""

from pathlib import Path
from typing import NamedTuple


class FolderLayer(NamedTuple):
    """The release a layer's answers file cannot name, read from its folder.

    Copier records ``_commit`` only for a template that is a git repository, so
    a layer rendered from a plain folder has nothing in its answers file to read
    a version from.

    Attributes:
        name: The layer's name.
        version: The version the folder's ``boilerplate.yml`` declares.
        path: The template folder the layer rendered from.
    """

    name: str
    version: str
    path: Path
