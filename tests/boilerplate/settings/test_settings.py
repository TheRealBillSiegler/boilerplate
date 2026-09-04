"""Unit tests for Settings - behavior-driven tests for configuration management."""

from pathlib import Path

import pytest
from pydantic import ValidationError
from pydantic_settings import SettingsError
from pytest import MonkeyPatch

from boilerplate.settings import Settings


class TestSettingsDefaultBehavior:
    """Settings provides sensible defaults for template discovery and logging."""

    def test_provides_default_template_directory_within_package(self) -> None:
        """Settings points to bundled templates by default."""
        settings = Settings()

        assert settings.default_templates_dir.name == "templates"
        assert settings.default_templates_dir.parent.name == "boilerplate"
        assert settings.default_templates_dir.is_absolute()

    def test_provides_user_specific_log_directory(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Settings creates log directory in user's home by default."""
        monkeypatch.setattr(Path, "home", classmethod(lambda _: tmp_path))
        settings = Settings()

        expected_log_dir = tmp_path / ".boilerplate" / "logs"
        assert settings.log_dir == expected_log_dir

    def test_disables_optional_features_by_default(self) -> None:
        """Settings starts with conservative defaults for optional features."""
        settings = Settings()

        assert settings.extra_template_dirs == []
        assert settings.file_logging_enabled is False
        assert settings.debug is False


class TestSettingsTemplateDirectoryResolution:
    """Settings enables flexible template directory configuration."""

    def test_allows_extending_template_search_paths_via_constructor(self) -> None:
        """Users can specify additional template directories during initialization."""
        extra_dirs = [Path("custom/templates"), Path("/opt/shared/templates")]
        settings = Settings(extra_template_dirs=extra_dirs)

        assert settings.extra_template_dirs == extra_dirs

    def test_consolidates_all_template_directories_in_resolution_order(self) -> None:
        """Combines default and extra template directories for resolution."""
        extra_dirs = [Path("custom1"), Path("custom2")]
        settings = Settings(extra_template_dirs=extra_dirs)

        expected_dirs = [settings.default_templates_dir, *extra_dirs]
        assert settings.template_dirs == expected_dirs

    def test_caches_template_directory_resolution(self) -> None:
        """template_dirs property uses cached_property for performance."""
        settings = Settings(extra_template_dirs=[Path("test")])

        # Access twice to verify caching behavior
        first_access = settings.template_dirs
        second_access = settings.template_dirs

        assert first_access is second_access  # Same object reference indicates caching


class TestSettingsEnvironmentVariableIntegration:
    """Settings respects environment variable overrides for configuration."""

    @pytest.mark.parametrize(
        ("env_value", "expected_paths"),
        [
            ('["custom", "shared"]', [Path("custom"), Path("shared")]),
            ('["single/path"]', [Path("single/path")]),
            ("[]", []),
        ],
        ids=["multiple-directories", "single-directory", "empty-list"],
    )
    def test_parses_template_directories_from_json_environment_variable(
        self, monkeypatch: MonkeyPatch, env_value: str, expected_paths: list[Path]
    ) -> None:
        """BOILERPLATE_EXTRA_TEMPLATE_DIRS accepts JSON array of directory paths."""
        monkeypatch.setenv("BOILERPLATE_EXTRA_TEMPLATE_DIRS", env_value)
        settings = Settings()

        assert settings.extra_template_dirs == expected_paths

    @pytest.mark.parametrize(
        ("env_var", "env_value", "setting_attr", "expected_value"),
        [
            ("BOILERPLATE_DEBUG", "true", "debug", True),
            ("BOILERPLATE_DEBUG", "false", "debug", False),
            ("BOILERPLATE_DEBUG", "1", "debug", True),
            ("BOILERPLATE_DEBUG", "0", "debug", False),
            ("BOILERPLATE_FILE_LOGGING_ENABLED", "true", "file_logging_enabled", True),
            (
                "BOILERPLATE_FILE_LOGGING_ENABLED",
                "false",
                "file_logging_enabled",
                False,
            ),
            ("BOILERPLATE_FILE_LOGGING_ENABLED", "yes", "file_logging_enabled", True),
            ("BOILERPLATE_FILE_LOGGING_ENABLED", "no", "file_logging_enabled", False),
        ],
        ids=[
            "debug-true-str",
            "debug-false-str",
            "debug-true-int",
            "debug-false-int",
            "logging-true-str",
            "logging-false-str",
            "logging-yes-str",
            "logging-no-str",
        ],
    )
    def test_interprets_boolean_environment_variables_flexibly(
        self,
        monkeypatch: MonkeyPatch,
        env_var: str,
        env_value: str,
        setting_attr: str,
        expected_value: bool,
    ) -> None:
        """Accept various truthy/falsy environment variable representations."""
        monkeypatch.setenv(env_var, env_value)
        settings = Settings()

        assert getattr(settings, setting_attr) is expected_value

    def test_overrides_log_directory_from_environment(
        self, monkeypatch: MonkeyPatch, tmp_path: Path
    ) -> None:
        """BOILERPLATE_LOG_DIR allows custom log directory specification."""
        custom_log_dir = tmp_path / "custom_logs"
        monkeypatch.setenv("BOILERPLATE_LOG_DIR", str(custom_log_dir))

        settings = Settings()
        assert settings.log_dir == custom_log_dir


class TestSettingsErrorHandling:
    """Settings handles malformed configuration gracefully."""

    @pytest.mark.parametrize(
        "invalid_json",
        [
            "not-json-at-all",
            '["unclosed array',
        ],
        ids=["plain-text", "malformed-json"],
    )
    def test_rejects_malformed_json_in_template_directories_environment_variable(
        self, monkeypatch: MonkeyPatch, invalid_json: str
    ) -> None:
        """Invalid JSON in BOILERPLATE_EXTRA_TEMPLATE_DIRS raises settings error."""
        monkeypatch.setenv("BOILERPLATE_EXTRA_TEMPLATE_DIRS", invalid_json)

        with pytest.raises(SettingsError, match="extra_template_dirs"):
            Settings()

    def test_rejects_wrong_json_type_in_template_directories_environment_variable(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        """Valid JSON, wrong type in BOILERPLATE_EXTRA_TEMPLATE_DIRS raises error."""
        monkeypatch.setenv("BOILERPLATE_EXTRA_TEMPLATE_DIRS", '{"not": "an array"}')

        with pytest.raises(ValidationError, match="extra_template_dirs"):
            Settings()

    def test_accepts_null_as_empty_list_in_template_directories(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        """JSON null in BOILERPLATE_EXTRA_TEMPLATE_DIRS is treated as empty list."""
        monkeypatch.setenv("BOILERPLATE_EXTRA_TEMPLATE_DIRS", "null")
        settings = Settings()

        assert settings.extra_template_dirs == []

    @pytest.mark.parametrize(
        "invalid_boolean",
        ["maybe", "yes-but-no", "2", "-1"],
        ids=[
            "ambiguous-text",
            "hyphenated-text",
            "non-binary-number",
            "negative-number",
        ],
    )
    def test_rejects_ambiguous_boolean_environment_variables(
        self, monkeypatch: MonkeyPatch, invalid_boolean: str
    ) -> None:
        """Ambiguous boolean values in environment variables raise validation errors."""
        monkeypatch.setenv("BOILERPLATE_DEBUG", invalid_boolean)

        with pytest.raises(ValidationError, match="debug"):
            Settings()
