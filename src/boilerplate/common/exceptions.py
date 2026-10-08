"""Canonical exceptions for the Boilerplate ecosystem.

This module defines the package-wide exception hierarchy. Import exceptions
from this module to ensure consistent behavior across the codebase and tests.
"""
# Spec: docs/design/02-data-models.md §Error Hierarchy


class BoilerplateError(Exception):
    """Base error for the Boilerplate ecosystem.

    Every concrete subclass carries a stable ``BP_{PHASE}_{DESCRIPTOR}`` code
    registered in docs/design/07-operational-quality.md §Error Code Registry,
    plus that registry's severity and retryable metadata.

    Attributes:
        severity: Registry severity classification for this error.
        retryable: Whether the failed operation may be retried, per
            docs/design/07-operational-quality.md §Retry Policy. Validation,
            not-found, and conflict errors are never retryable.

    Args:
        message: Human-readable error description.
        error_code: Machine-readable error code
            (e.g. "BP_RESOLVE_TEMPLATE_NOT_FOUND").
        remediation: Suggested fix for the user.
    """

    severity: str = "error"
    retryable: bool = False

    def __init__(
        self,
        message: str = "",
        *,
        error_code: str | None = None,
        remediation: str | None = None,
    ) -> None:
        """Initialize with optional error code and remediation."""
        super().__init__(message)
        self.error_code = error_code
        self.remediation = remediation


class ActionRequiredError(BoilerplateError):
    """Base for recoverable workflow pauses that require user intervention.

    Routed to exit code 4 (ACTION_REQUIRED) by the CLI error boundary, per
    docs/design/02-data-models.md §Exit Codes: the operation cannot complete
    until the user acts (e.g. resolving update merge conflicts before
    ``--continue``), which is distinct from a hard failure (exit 1).
    Concrete pause conditions subclass this with their own error code.
    """


class DirectoryValidationError(BoilerplateError):
    """Raised when a directory path fails validation (missing, not a dir, etc.)."""

    def __init__(self, message: str = "", **kwargs: str | None) -> None:
        """Initialize with default error code BP_CONFIG_DIR_INVALID."""
        super().__init__(message, error_code="BP_CONFIG_DIR_INVALID", **kwargs)


class TemplateNotFoundError(BoilerplateError):
    """Raised when a requested template cannot be located in any catalog path."""

    def __init__(self, message: str = "", **kwargs: str | None) -> None:
        """Initialize with default error code BP_RESOLVE_TEMPLATE_NOT_FOUND."""
        super().__init__(
            message,
            error_code="BP_RESOLVE_TEMPLATE_NOT_FOUND",
            remediation=kwargs.pop(
                "remediation",
                "Run 'boilerplate list' to see available templates.",
            ),
            **kwargs,
        )


class InvalidVersionError(BoilerplateError):
    """Raised when a provided version string is not PEP 440 compliant."""

    def __init__(self, message: str = "", **kwargs: str | None) -> None:
        """Initialize with default error code BP_VERSION_INVALID."""
        super().__init__(message, error_code="BP_VERSION_INVALID", **kwargs)


class DestinationNotEmptyError(BoilerplateError):
    """Raised when the destination directory exists and is not empty without force."""

    def __init__(self, message: str = "", **kwargs: str | None) -> None:
        """Initialize with default error code BP_RENDER_DEST_NOT_EMPTY."""
        super().__init__(
            message,
            error_code="BP_RENDER_DEST_NOT_EMPTY",
            remediation=kwargs.pop("remediation", "Use --force to overwrite."),
            **kwargs,
        )


class NonInteractiveRequiresForceError(BoilerplateError):
    """Raised when a multi-layer render in non-interactive mode requires --force."""

    def __init__(self, message: str = "", **kwargs: str | None) -> None:
        """Initialize with default error code BP_INPUT_FORCE_REQUIRED."""
        super().__init__(
            message,
            error_code="BP_INPUT_FORCE_REQUIRED",
            remediation=kwargs.pop("remediation", "Add --force to proceed."),
            **kwargs,
        )


class InvalidTemplateSpecifierError(BoilerplateError):
    """Raised when a template specifier (name@version) fails validation.

    This includes invalid template names, malformed specifier strings, or
    unsupported value types when converting to a TemplateSpecifier.
    """

    def __init__(self, message: str = "", **kwargs: str | None) -> None:
        """Initialize with default error code BP_INPUT_SPECIFIER_INVALID."""
        super().__init__(
            message,
            error_code="BP_INPUT_SPECIFIER_INVALID",
            remediation=kwargs.pop("remediation", "Use format: name or name@version."),
            **kwargs,
        )


class MetadataValidationError(BoilerplateError):
    """Raised when template metadata is invalid or inconsistent.

    For example, an invalid ``boilerplate.yml``.
    """

    def __init__(self, message: str = "", **kwargs: str | None) -> None:
        """Initialize with default error code BP_RESOLVE_METADATA_INVALID."""
        super().__init__(message, error_code="BP_RESOLVE_METADATA_INVALID", **kwargs)


class MissingRequiredAnswersError(BoilerplateError):
    """Raised when required answers are missing for non-interactive render.

    Emitted before Copier is invoked. A question is "required" when it has
    no ``default`` and no ``when: false``; in interactive mode Copier would
    prompt, but in ``--ci`` / ``--non-interactive`` mode there is no one to
    answer, so the render must fail fast with a clear enumeration of the
    unanswered fields.
    """

    def __init__(self, message: str = "", **kwargs: str | None) -> None:
        """Initialize with default error code BP_INPUT_ANSWERS_MISSING."""
        super().__init__(
            message,
            error_code="BP_INPUT_ANSWERS_MISSING",
            remediation=kwargs.pop(
                "remediation",
                "Supply the missing values with --data key=value or "
                "--data-file <path> (a YAML mapping), add defaults for these "
                "questions in the template's copier.yml, or run without "
                "--ci / --non-interactive to prompt interactively.",
            ),
            **kwargs,
        )


class InvalidDataError(BoilerplateError):
    """Raised when ``--data`` or ``--data-file`` input cannot be parsed.

    Emitted before Copier is invoked, covering the parse failures ahead of
    any render attempt: a ``--data`` entry with no ``=`` separator, a
    ``--data-file`` path that cannot be read (including as UTF-8) or whose
    YAML is malformed, data-file content that is not a YAML mapping, and a
    key (from either source) that is empty, starts with an underscore
    (Copier's reserved-directive namespace), or — for ``--data-file`` — is
    not a string.
    """

    def __init__(self, message: str = "", **kwargs: str | None) -> None:
        """Initialize with default error code BP_INPUT_DATA_INVALID."""
        super().__init__(
            message,
            error_code="BP_INPUT_DATA_INVALID",
            remediation=kwargs.pop(
                "remediation",
                "Use --data key=value (repeatable) for individual answers, "
                "or --data-file <path> for a UTF-8 YAML mapping of question "
                "name to answer.",
            ),
            **kwargs,
        )


class RecordedAnswerRejectedError(BoilerplateError):
    """Raised when a layer's update step finds a recorded answer its target rejects.

    The check runs inside the layer's step, after the layer's migrations and
    Copier's re-read of the answers file, so a migration that repairs a
    recorded answer clears it first. The target view's question rejects the
    answer by type, choices or validator; Copier would otherwise drop it and
    record the new default without a word.

    Attributes:
        layer: The layer whose answers file records the answer.
        question: The question the answer is for.
        value: The recorded answer.
        reason: Why the target view's question rejects it.
    """

    def __init__(
        self,
        message: str = "",
        *,
        layer: str = "",
        question: str = "",
        value: object = None,
        reason: str = "",
        **kwargs: str | None,
    ) -> None:
        """Initialize with default error code BP_INPUT_ANSWER_REJECTED."""
        super().__init__(
            message,
            error_code="BP_INPUT_ANSWER_REJECTED",
            remediation=kwargs.pop(
                "remediation",
                f"Pass a valid value with --set {question or '<question>'}=<value>.",
            ),
            **kwargs,
        )
        self.layer = layer
        self.question = question
        self.value = value
        self.reason = reason


class InteractiveModeRequiresTtyError(BoilerplateError):
    """Raised when an interactive render is requested but stdin is not a TTY.

    Raised by the ``new`` command's pre-flight, before its Copier
    invocation. Without this pre-flight, Copier's
    prompt layer (questionary/prompt_toolkit) can retry-loop on EOF instead
    of raising, growing memory without bound in environments that can never
    answer a prompt (CI pipelines, piped input, sessions without a console).
    """

    def __init__(self, message: str = "", **kwargs: str | None) -> None:
        """Initialize with default error code BP_INPUT_TTY_REQUIRED."""
        super().__init__(
            message,
            error_code="BP_INPUT_TTY_REQUIRED",
            remediation=kwargs.pop(
                "remediation",
                "Pass --non-interactive to render with defaults "
                "(or use the global flag: boilerplate --ci new ...), or "
                "run from an interactive terminal; --data/--data-file "
                "answers are preserved and used under --non-interactive.",
            ),
            **kwargs,
        )


class DestinationRequiredError(BoilerplateError):
    """Raised when a non-interactive render names no destination.

    Raised by the ``new`` command before its Copier invocation. With no
    prompt to ask, the only fallback would be the current directory, and a
    render into whatever directory a pipeline happens to run in is the
    outcome docs/design/05-cli-reference.md (Destination behavior) rules out.
    """

    def __init__(self, message: str = "", **kwargs: str | None) -> None:
        """Initialize with default error code BP_INPUT_DEST_REQUIRED."""
        super().__init__(
            message,
            error_code="BP_INPUT_DEST_REQUIRED",
            remediation=kwargs.pop(
                "remediation",
                "Pass the destination directory as the second argument: "
                "boilerplate new <template> <destination>.",
            ),
            **kwargs,
        )


class InteractiveRenderFailedError(BoilerplateError):
    """Raised when Copier's prompt machinery failed because prompting is impossible.

    Emitted as a translation of prompt_toolkit / questionary failures during
    rendering (e.g., Windows ``NoConsoleScreenBufferError`` under a Git Bash
    pseudo-TTY). The underlying cause is a terminal that cannot host
    prompt_toolkit's output backend; the user's options are to switch to a
    real terminal or supply the missing answers up front.
    """

    def __init__(self, message: str = "", **kwargs: str | None) -> None:
        """Initialize with default error code BP_RENDER_PROMPT_FAILED."""
        super().__init__(
            message,
            error_code="BP_RENDER_PROMPT_FAILED",
            remediation=kwargs.pop(
                "remediation",
                "Re-run with --ci (implies --non-interactive) "
                "from a shell where all required answers have defaults, or use "
                "a terminal that supports interactive prompts (e.g., PowerShell "
                "on Windows, a real tty on Unix).",
            ),
            **kwargs,
        )


class UserCancelledError(BoilerplateError):
    """Raised when the user cancels an interactive render (e.g. Ctrl+C at a prompt).

    Translated from Copier's ``CopierAnswersInterrupt``, which subclasses both
    ``CopierError`` and ``KeyboardInterrupt`` and carries the full
    ``(AnswersMap, Question, Template)`` tuple as its args; stringifying it
    directly would leak collected answers and absolute template paths to the
    terminal. Never retryable: retrying would override the user's explicit
    choice to stop.
    """

    def __init__(self, message: str = "Aborted.", **kwargs: str | None) -> None:
        """Initialize with default error code BP_RENDER_USER_CANCELLED."""
        super().__init__(message, error_code="BP_RENDER_USER_CANCELLED", **kwargs)
