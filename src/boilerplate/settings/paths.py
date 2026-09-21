r"""Platform-aware path helpers for boilerplate's per-user configuration files.

Windows uses ``%APPDATA%\boilerplate``; POSIX uses ``$XDG_CONFIG_HOME/boilerplate``
with a fallback to ``~/.config/boilerplate`` per the XDG base directory spec.
"""

import os
import sys
from pathlib import Path


def _config_root() -> Path:
    """Return the platform-specific boilerplate config root directory."""
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata is None:
            raise RuntimeError("%APPDATA% is not set; cannot locate config root.")
        return Path(appdata) / "boilerplate"

    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "boilerplate"
    return Path.home() / ".config" / "boilerplate"


def profile_toml_path() -> Path:
    """Return the path to the per-user ``profile.toml``."""
    return _config_root() / "profile.toml"
