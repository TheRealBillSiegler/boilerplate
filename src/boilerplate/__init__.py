"""Boilerplate: a Python development environment paired with layered templates.

Boilerplate pairs a Python development environment, one tool for each job, with
templates that build on one another to stamp out projects. Built on Copier.
"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as get_version

try:
    __version__ = get_version("boilerplate")
except PackageNotFoundError:
    __version__ = "Unknown"
