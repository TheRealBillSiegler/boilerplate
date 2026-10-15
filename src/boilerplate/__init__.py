"""Boilerplate: stamps out Python projects from templates that stack.

Built on Copier.
"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as get_version

try:
    __version__ = get_version("boilerplate")
except PackageNotFoundError:
    __version__ = "Unknown"
