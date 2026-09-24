"""Validators for CLI arguments."""

from pathlib import Path

from boilerplate.cli.common import TEMPLATE_DIRS_HINT
from boilerplate.common.exceptions import DirectoryValidationError


def validate_directory(path: Path) -> Path:
    """Ensure a directory exists and is a directory.

    Args:
        path: The directory to validate.

    Returns:
        The same path if valid.

    Raises:
        DirectoryValidationError: If the path does not exist or is not a
            directory.
    """
    try:
        if not path.exists():
            raise DirectoryValidationError(
                f"'{path}' does not exist.", remediation=TEMPLATE_DIRS_HINT
            )
        if not path.is_dir():
            raise DirectoryValidationError(
                f"'{path}' is not a directory.", remediation=TEMPLATE_DIRS_HINT
            )
    except (PermissionError, OSError) as e:
        raise DirectoryValidationError(
            f"Permission denied accessing directory '{path}': {e}"
        ) from e
    return path
