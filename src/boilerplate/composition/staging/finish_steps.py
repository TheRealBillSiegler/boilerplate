"""The steps of an update or an add that the shared finisher runs for it."""

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class FinishSteps:
    """What one operation does after its copy back, for the finisher to sequence.

    A paused update supplies only its record: the finisher's kind branch, not
    these steps, decides that a paused run runs no tasks and writes no lock.

    Attributes:
        write_record: Appends the run's one migration record.
        write_lock: Writes the lock a complete run ends with; ``None`` for a
            paused run.
        run_tasks: Runs the tasks in the user's checkout and returns whether
            the files are kept. It returns ``False`` after it undid the run, when
            a task failed and the user chose to undo. ``None`` for a paused run.
    """

    write_record: Callable[[], None]
    write_lock: Callable[[], None] | None = None
    run_tasks: Callable[[], bool] | None = None
