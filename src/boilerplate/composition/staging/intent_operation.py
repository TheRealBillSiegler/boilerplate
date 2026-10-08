"""The operations an intent journal can belong to."""

from enum import StrEnum


class IntentOperation(StrEnum):
    """The mutating operation that owns an intent journal.

    Crash recovery dispatches on it to the operation-specific handler.
    """

    CREATE = "create"
    UPDATE = "update"
    ADD = "add"
    ADOPT = "adopt"
    ENV_APPLY = "env_apply"
