"""Profile: per-user default answers for template Questions.

Read from ``profile.toml`` at the boilerplate config root. The file's
grammar is two reserved tables — ``[defaults]`` (applies to any template)
and ``[templates.<name>]`` (applies to one template, overriding
``[defaults]``). Keys are open: they are template Question names and are
never validated here; a key matching no Question is simply unused by
rendering.
"""

import tomllib
from typing import Any

from boilerplate.common.exceptions import BoilerplateError
from boilerplate.settings.paths import profile_toml_path


class ProfileError(BoilerplateError):
    """Raised when ``profile.toml`` exists but cannot be read as expected."""

    def __init__(self, message: str = "", **kwargs: str | None) -> None:
        """Initialize with default error code BP_CONFIG_PROFILE_INVALID."""
        super().__init__(message, error_code="BP_CONFIG_PROFILE_INVALID", **kwargs)


def _require_table(value: object, name: str) -> dict[str, Any]:
    """Return ``value`` as a table, treating absence as empty.

    Args:
        value: The raw TOML value for the section.
        name: Dotted section name, used in the error message.

    Returns:
        The section as a dict (empty when the section is absent).

    Raises:
        ProfileError: If the section exists but is not a table.
    """
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ProfileError(f"profile.toml [{name}] must be a table.")
    return value


def load_profile(template_name: str) -> dict[str, Any]:
    """Load default answers for ``template_name`` from ``profile.toml``.

    Args:
        template_name: The invoked template's name (selects
            ``[templates.<name>]``).

    Returns:
        ``[defaults]`` overlaid by ``[templates.<template_name>]``. Empty
        when the file does not exist.

    Raises:
        ProfileError: If the file exists but is not valid TOML, or a
            reserved section is not a table.
    """
    path = profile_toml_path()
    if not path.is_file():
        return {}
    try:
        with path.open("rb") as fp:
            data = tomllib.load(fp)
    except tomllib.TOMLDecodeError as exc:
        raise ProfileError(f"{path} is not valid TOML: {exc}") from exc

    merged = dict(_require_table(data.get("defaults"), "defaults"))
    templates = _require_table(data.get("templates"), "templates")
    merged.update(
        _require_table(templates.get(template_name), f"templates.{template_name}")
    )
    return merged


__all__ = ["ProfileError", "load_profile"]
