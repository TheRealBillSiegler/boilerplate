"""Jinja extension that derives Python package names from project names."""

import re

from jinja2 import Environment
from jinja2.ext import Extension


def to_package(value: object) -> str:
    """Convert `value` to a valid Python package name.

    Args:
        value: The human-readable project name.

    Returns:
        The name lower-cased, with each run of other characters replaced by one
        underscore and a leading underscore added before a leading digit.
    """
    name = re.sub(r"[^0-9a-z]+", "_", str(value).lower()).strip("_")
    return f"_{name}" if name[:1].isdigit() else name


class PackageNameExtension(Extension):
    """Register the ``to_package`` filter in a Jinja environment."""

    def __init__(self, environment: Environment) -> None:
        """Add the ``to_package`` filter to `environment`.

        Args:
            environment: The Jinja environment to augment.
        """
        super().__init__(environment)
        environment.filters["to_package"] = to_package
