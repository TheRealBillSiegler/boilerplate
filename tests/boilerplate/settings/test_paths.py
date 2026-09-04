"""Unit tests for platform-aware per-user config path helpers."""

from boilerplate.settings.paths import profile_toml_path


def test_profile_toml_path_is_under_config_root() -> None:
    assert profile_toml_path().name == "profile.toml"
    assert profile_toml_path().parent.name == "boilerplate"
