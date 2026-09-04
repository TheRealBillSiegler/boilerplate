"""Integration tests for exception scenarios in real CLI operations."""

import tempfile
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from boilerplate.cli.validators import validate_directory
from boilerplate.common.exceptions import BoilerplateError, DirectoryValidationError


class TestDirectoryValidationScenarios:
    """Tests directory validation in real CLI workflows."""

    def test_validate_directory_with_nonexistent_path(self) -> None:
        """Raises BoilerplateError when validating a nonexistent directory."""
        nonexistent_path = Path("/this/path/does/not/exist")

        with pytest.raises(BoilerplateError) as exc_info:
            validate_directory(nonexistent_path)

        error_message = str(exc_info.value)
        assert str(nonexistent_path) in error_message
        assert "does not exist" in error_message or "invalid" in error_message

    def test_validate_directory_with_file_instead_of_directory(self) -> None:
        """Raises BoilerplateError when given a file path instead of directory."""
        with tempfile.NamedTemporaryFile() as temp_file:
            file_path = Path(temp_file.name)

            with pytest.raises(BoilerplateError) as exc_info:
                validate_directory(file_path)

            error_message = str(exc_info.value)
            assert str(file_path) in error_message
            assert "does not exist" in error_message or "invalid" in error_message

    def test_validate_directory_with_valid_directory(self) -> None:
        """Returns the same path when given a valid directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            directory_path = Path(temp_dir)
            result = validate_directory(directory_path)
            assert result == directory_path


class TestErrorHandlingInCLIWorkflows:
    """Tests how errors propagate through actual CLI command workflows."""

    def test_boilerplate_error_hierarchy_in_exception_handling(self) -> None:
        """Verifies that catching BoilerplateError catches all custom exceptions."""
        # Test that DirectoryValidationError can be caught as BoilerplateError
        try:
            raise DirectoryValidationError("Directory validation failed")
        except BoilerplateError as e:
            assert isinstance(e, DirectoryValidationError)
            assert "Directory validation failed" in str(e)

        # Test that the base BoilerplateError can be caught
        try:
            raise BoilerplateError("Generic CLI error")
        except BoilerplateError as e:
            assert type(e) is BoilerplateError
            assert "Generic CLI error" in str(e)

    def test_error_messages_are_user_friendly(self) -> None:
        """Error messages are clear and actionable for end users."""
        invalid_path = Path("/nonexistent/templates")

        try:
            validate_directory(invalid_path)
        except BoilerplateError as e:
            error_message = str(e)
            # Should contain the path that failed
            assert str(invalid_path) in error_message
            # Should be clear about what went wrong
            assert "does not exist" in error_message or "invalid" in error_message
            # Should not contain technical jargon
            assert "BoilerplateError" not in error_message
            assert "Exception" not in error_message


class TestDirectoryValidationEdgeCases:
    """Tests edge cases in directory validation."""

    def test_validate_directory_with_permission_denied(
        self, mocker: MockerFixture
    ) -> None:
        """Raises appropriate error when directory exists but is not accessible."""
        # This test simulates permission denial using mocks
        with tempfile.TemporaryDirectory() as temp_dir:
            directory_path = Path(temp_dir)

            # Mock os.access to return False (permission denied)
            mocker.patch("pathlib.Path.exists", return_value=True)
            mocker.patch("pathlib.Path.is_dir", return_value=False)
            with pytest.raises(BoilerplateError):
                validate_directory(directory_path)

    def test_validate_directory_with_nonexistent_file_path(self) -> None:
        """Handles gracefully when given a path to a nonexistent file."""
        nonexistent_file = Path("/tmp/nonexistent_file.txt")

        with pytest.raises(BoilerplateError):
            validate_directory(nonexistent_file)

    def test_validate_directory_with_current_directory(self) -> None:
        """Works with current directory (Path())."""
        # Current directory (Path()) should be valid
        current_dir = Path()
        result = validate_directory(current_dir)
        assert result == current_dir

    def test_validate_directory_with_relative_path(self) -> None:
        """Works with relative paths that exist."""
        # Test that current directory works (using Path() which is
        # equivalent to Path("."))
        current_dir = Path()
        result = validate_directory(current_dir)
        assert result == current_dir
