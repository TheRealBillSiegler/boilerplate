"""Graph domain exceptions."""

from boilerplate.common.exceptions import BoilerplateError


class DependencyError(BoilerplateError):
    """Base error for dependency resolution failures."""


class DependencyNotFoundError(DependencyError):
    """Raised when a referenced template cannot be found."""

    def __init__(self, message: str = "", **kwargs: str | None) -> None:
        """Initializes with default error code BP_RESOLVE_DEP_NOT_FOUND."""
        super().__init__(message, error_code="BP_RESOLVE_DEP_NOT_FOUND", **kwargs)


class DependencyCycleError(DependencyError):
    """Raised when dependencies contain a cycle during ordering or normalization."""

    def __init__(self, message: str = "", **kwargs: str | None) -> None:
        """Initializes with default error code BP_GRAPH_CYCLE."""
        super().__init__(message, error_code="BP_GRAPH_CYCLE", **kwargs)


class VersionConflictError(DependencyError):
    """Raised when the same template name resolves to different versions in a graph."""

    def __init__(self, message: str = "", **kwargs: str | None) -> None:
        """Initializes with default error code BP_RESOLVE_VERSION_CONFLICT."""
        super().__init__(
            message,
            error_code="BP_RESOLVE_VERSION_CONFLICT",
            remediation=kwargs.pop(
                "remediation",
                "Align all references to a single version, or use version "
                "ranges that resolve to a common version.",
            ),
            **kwargs,
        )
