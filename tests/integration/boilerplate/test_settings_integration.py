"""Integration tests for Settings - real filesystem and .env file interactions."""

from pathlib import Path
from textwrap import dedent

import pytest

from boilerplate.settings import Settings


class TestSettingsRealFilesystemIntegration:
    """Settings integrates correctly with real filesystem structures."""

    def test_resolves_default_template_directory_to_actual_bundled_templates(
        self,
    ) -> None:
        """Settings default template directory points to actual bundled templates."""
        settings = Settings()

        # Verify the default templates directory exists and contains expected templates
        assert settings.default_templates_dir.exists()
        assert settings.default_templates_dir.is_dir()

        # Should contain at least the project and streamlit templates
        template_names = [
            p.name for p in settings.default_templates_dir.iterdir() if p.is_dir()
        ]
        expected_templates = {"project", "streamlit"}
        assert expected_templates.issubset(set(template_names))

    def test_template_dirs_property_works_with_real_directories(
        self, tmp_path: Path
    ) -> None:
        """template_dirs property correctly combines real and extra directories."""
        # Create some real extra directories
        extra1 = tmp_path / "extra1"
        extra2 = tmp_path / "extra2"
        extra1.mkdir()
        extra2.mkdir()

        settings = Settings(extra_template_dirs=[extra1, extra2])

        # All directories should be included in resolution order
        resolved_dirs = settings.template_dirs
        assert len(resolved_dirs) == 3  # default + 2 extra
        assert resolved_dirs[0] == settings.default_templates_dir
        assert resolved_dirs[1] == extra1
        assert resolved_dirs[2] == extra2

        # All directories should exist
        for directory in resolved_dirs:
            assert directory.exists()

    def test_log_directory_creation_behavior(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Settings log directory behavior with real filesystem paths."""
        # Mock user home to our tmp directory
        monkeypatch.setattr(Path, "home", classmethod(lambda _: tmp_path))

        settings = Settings()
        expected_log_dir = tmp_path / ".boilerplate" / "logs"

        assert settings.log_dir == expected_log_dir
        # Log directory should not be created by Settings itself
        assert not settings.log_dir.exists()


class TestSettingsEnvironmentFileIntegration:
    """Settings integrates with .env files for configuration."""

    def test_loads_configuration_from_env_file_in_current_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Settings loads configuration from .env file when present."""
        # Create a .env file with boilerplate configuration
        env_file = tmp_path / ".env"
        env_content = dedent("""
            BOILERPLATE_DEBUG=true
            BOILERPLATE_FILE_LOGGING_ENABLED=true
            BOILERPLATE_EXTRA_TEMPLATE_DIRS=["custom", "shared"]
        """).strip()
        env_file.write_text(env_content)

        # Change to the directory with the .env file
        monkeypatch.chdir(tmp_path)

        settings = Settings()

        assert settings.debug is True
        assert settings.file_logging_enabled is True
        assert settings.extra_template_dirs == [Path("custom"), Path("shared")]

    def test_environment_variables_override_env_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Environment variables take precedence over .env file settings."""
        # Create .env file with one value
        env_file = tmp_path / ".env"
        env_file.write_text("BOILERPLATE_DEBUG=false")

        # Set conflicting environment variable
        monkeypatch.setenv("BOILERPLATE_DEBUG", "true")
        monkeypatch.chdir(tmp_path)

        settings = Settings()

        # Environment variable should win
        assert settings.debug is True

    def test_works_without_env_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Settings works correctly when no .env file is present."""
        # Ensure we're in a directory without .env file
        monkeypatch.chdir(tmp_path)

        settings = Settings()

        # Should get default values
        assert settings.debug is False
        assert settings.file_logging_enabled is False
        assert settings.extra_template_dirs == []


class TestSettingsMultiDirectoryIntegration:
    """Settings works correctly with complex multi-directory template setups."""

    def test_template_directory_resolution_with_mixed_existing_and_missing_directories(
        self, tmp_path: Path
    ) -> None:
        """Settings handles mixed existing and missing template directories."""
        # Create one real directory, reference one that doesn't exist
        existing_dir = tmp_path / "exists"
        existing_dir.mkdir()
        missing_dir = tmp_path / "missing"

        settings = Settings(extra_template_dirs=[existing_dir, missing_dir])

        # template_dirs should include all specified directories regardless of existence
        resolved_dirs = settings.template_dirs
        assert existing_dir in resolved_dirs
        assert missing_dir in resolved_dirs

        # But only existing_dir should actually exist
        assert existing_dir.exists()
        assert not missing_dir.exists()

    def test_template_directories_with_absolute_and_relative_paths(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Settings correctly handles mix of absolute and relative paths."""
        # Create test directories
        abs_dir = tmp_path / "absolute"
        abs_dir.mkdir()

        rel_dir = tmp_path / "relative"
        rel_dir.mkdir()

        # Change to tmp_path so relative path works
        monkeypatch.chdir(tmp_path)

        settings = Settings(extra_template_dirs=[abs_dir, Path("relative")])

        resolved_dirs = settings.template_dirs

        # Both should be in the resolved list
        assert abs_dir in resolved_dirs
        # The relative path should resolve to our relative directory
        assert any(d.name == "relative" for d in resolved_dirs)


class TestSettingsProductionScenarios:
    """Settings behavior in production-like scenarios."""

    def test_settings_with_complex_real_world_configuration(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Settings handles complex real-world configuration scenarios."""
        # Set up a realistic directory structure
        home_dir = tmp_path / "home"
        project_dir = tmp_path / "project"
        shared_templates = tmp_path / "shared_templates"

        for directory in [home_dir, project_dir, shared_templates]:
            directory.mkdir(parents=True)

        # Create .env file in project - use forward slashes for JSON compatibility
        env_file = project_dir / ".env"
        # Convert Windows path to forward slashes for JSON compatibility
        shared_templates_str = str(shared_templates).replace("\\", "/")
        log_dir_str = str(home_dir / ".boilerplate" / "logs").replace("\\", "/")

        env_content = dedent(f"""
            BOILERPLATE_EXTRA_TEMPLATE_DIRS=["{shared_templates_str}"]
            BOILERPLATE_LOG_DIR={log_dir_str}
            BOILERPLATE_FILE_LOGGING_ENABLED=true
            BOILERPLATE_DEBUG=false
        """).strip()
        env_file.write_text(env_content)

        # Mock environment
        monkeypatch.chdir(project_dir)
        monkeypatch.setattr(Path, "home", classmethod(lambda _: home_dir))

        settings = Settings()

        # Verify complex configuration is loaded correctly
        assert settings.extra_template_dirs == [Path(shared_templates_str)]
        assert settings.log_dir == Path(log_dir_str)
        assert settings.file_logging_enabled is True
        assert settings.debug is False

        # template_dirs should include both default and shared templates
        assert len(settings.template_dirs) == 2
        assert settings.default_templates_dir in settings.template_dirs
        assert Path(shared_templates_str) in settings.template_dirs
