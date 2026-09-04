"""Constants for the Boilerplate CLI."""

from enum import IntEnum


class ExitCode(IntEnum):
    """Standardized CLI exit codes.

    The canonical six-value set is defined in docs/design/02-data-models.md
    §Exit Codes; the coarse-codes-plus-BP* principle is
    docs/design/adr-004-exit-code-taxonomy.md. ACTION_REQUIRED marks
    recoverable workflow pauses that need user intervention, as distinct
    from hard failures (FAILURE).
    """

    SUCCESS = 0
    FAILURE = 1
    CONFIG_ERROR = 2
    VALIDATION_ERROR = 3
    ACTION_REQUIRED = 4
    # 130 = 128 + SIGINT, the POSIX convention Typer's own KeyboardInterrupt
    # handler already uses (see typer.core), so every Ctrl+C in this app
    # exits with one shared code.
    USER_CANCELLED = 130
