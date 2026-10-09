"""The steps of an update or an add that the shared finisher runs for it."""

from collections.abc import Callable
from dataclasses import dataclass


def _keep_files() -> bool:
    """Report that there are no tasks to fail, so the files are kept."""
    return True


def _write_nothing() -> None:
    """Stand in for the lock of a run that writes none."""


@dataclass(frozen=True)
class FinishSteps:
    """What one operation does after its copy back, for the finisher to sequence.

    Attributes:
        write_record: Appends the run's one migration record.
        write_lock: Writes the lock the run ends with; a paused update writes
            none, so it keeps the default.
        run_tasks: Runs the tasks in the user's checkout and returns whether
            the files are kept. It returns ``False`` after it undid the run, when
            a task failed and the user chose to undo; the default, for a run
            without tasks, keeps them.
    """

    write_record: Callable[[], None]
    write_lock: Callable[[], None] = _write_nothing
    run_tasks: Callable[[], bool] = _keep_files
