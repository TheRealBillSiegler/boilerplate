"""Tests for CLI argument validation helpers."""

from pathlib import Path

import pytest

from boilerplate.cli.validators import validate_directory
from boilerplate.common.exceptions import BoilerplateError


def test_validate_existing_directory(tmp_path: Path):
    """Tests that validate_directory returns path unchanged for existing directories."""
    result = validate_directory(tmp_path)
    assert result == tmp_path, f"Should return input path {tmp_path}, got {result}"


def test_validate_missing_directory(tmp_path: Path):
    """Tests that validate_directory raises BoilerplateError for missing directories."""
    non_existent = tmp_path / "nope"
    with pytest.raises(BoilerplateError, match="does not exist"):
        validate_directory(non_existent)


def test_validate_path_is_file(tmp_path: Path):
    """Tests that validate_directory raises BoilerplateError when path is a file."""
    path = tmp_path / "somefile"
    path.write_text("not a directory")
    with pytest.raises(BoilerplateError, match="does not exist or is invalid"):
        validate_directory(path)
