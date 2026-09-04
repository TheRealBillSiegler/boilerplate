"""Boilerplate settings package."""

from boilerplate.settings.profile import ProfileError, load_profile
from boilerplate.settings.settings import Settings

__all__ = [
    "ProfileError",
    "Settings",
    "load_profile",
]
