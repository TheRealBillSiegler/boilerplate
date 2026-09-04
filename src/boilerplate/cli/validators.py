"""Validators for CLI arguments."""

from pathlib import Path

from boilerplate.common.exceptions import DirectoryValidationError


def validate_directory(path: Path) -> Path:
    """Ensures a directory exists and is a directory.

    Args:
        path: The directory to validate.

    Returns:
        The same path if valid.

    Raises:
        DirectoryValidationError: If the directory does not exist or is invalid.
    """
    try:
        if not path.exists() or not path.is_dir():
            raise DirectoryValidationError(
                f"Directory '{path}' does not exist or is invalid."
            )
    except (PermissionError, OSError) as e:
        raise DirectoryValidationError(
            f"Permission denied accessing directory '{path}': {e}"
        ) from e
    return path
