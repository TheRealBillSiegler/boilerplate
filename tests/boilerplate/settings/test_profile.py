"""Tests for Profile loading (profile.toml)."""

from pathlib import Path

import pytest

from boilerplate.settings.profile import ProfileError, load_profile


@pytest.fixture
def profile_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Points the loader at a temp profile.toml and returns its path."""
    path = tmp_path / "profile.toml"
    monkeypatch.setattr("boilerplate.settings.profile.profile_toml_path", lambda: path)
    return path


class TestLoadProfile:
    @pytest.mark.usefixtures("profile_file")
    def test_missing_file_returns_empty_dict(self):
        # profile_file points the loader at a temp path that is never written,
        # so the file is absent and the loader must return {}.
        assert load_profile("project") == {}

    def test_global_defaults_apply_to_any_template(self, profile_file: Path):
        profile_file.write_text('[defaults]\nauthor_name = "Jane Dev"\n')
        assert load_profile("project") == {"author_name": "Jane Dev"}
        assert load_profile("streamlit") == {"author_name": "Jane Dev"}

    def test_template_section_overrides_defaults(self, profile_file: Path):
        profile_file.write_text(
            "[defaults]\n"
            'container_registry = "ghcr.io"\n'
            'author_name = "Jane Dev"\n'
            "\n"
            "[templates.streamlit]\n"
            'container_registry = "registry.example.com"\n'
        )
        assert load_profile("streamlit") == {
            "author_name": "Jane Dev",
            "container_registry": "registry.example.com",
        }
        # Other templates are untouched by [templates.streamlit].
        assert load_profile("project") == {
            "author_name": "Jane Dev",
            "container_registry": "ghcr.io",
        }

    def test_unmatched_keys_pass_through_unvalidated(self, profile_file: Path):
        profile_file.write_text('[defaults]\nno_such_question = "x"\n')
        assert load_profile("project") == {"no_such_question": "x"}

    def test_malformed_toml_raises(self, profile_file: Path):
        profile_file.write_text("not [ valid { toml")
        with pytest.raises(ProfileError, match="not valid TOML") as excinfo:
            load_profile("project")
        assert excinfo.value.error_code == "BP_CONFIG_PROFILE_INVALID"

    def test_non_table_reserved_section_raises(self, profile_file: Path):
        profile_file.write_text('defaults = "oops"\n')
        with pytest.raises(ProfileError, match=r"\[defaults\] must be a table"):
            load_profile("project")
