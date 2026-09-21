"""Merging domain exceptions."""

from boilerplate.common.exceptions import BoilerplateError


class MergeConflictError(BoilerplateError):
    """Raised when incompatible values are encountered during merging."""

    def __init__(self, message: str = "", **kwargs: str | None) -> None:
        """Initialize with default error code BP_RESOLVE_MERGE_CONFLICT."""
        super().__init__(message, error_code="BP_RESOLVE_MERGE_CONFLICT", **kwargs)
