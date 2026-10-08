"""The callback that decides what a failed task does to the update."""

from collections.abc import Callable

from boilerplate.composition.updating.failed_task import FailedTask
from boilerplate.composition.updating.task_failure_choice import TaskFailureChoice

TaskFailureHandler = Callable[[FailedTask], TaskFailureChoice]
"""Called with the failed task; returns whether to keep the files or undo."""


def keep_files(_failed: FailedTask) -> TaskFailureChoice:
    """Keep the files, as a caller that cannot ask does.

    Args:
        _failed: The failed task; not consulted.

    Returns:
        ``TaskFailureChoice.KEEP``.
    """
    return TaskFailureChoice.KEEP
