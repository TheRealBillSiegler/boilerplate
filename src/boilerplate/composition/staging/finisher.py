"""Finish an update or an add after its walk: the copy back and what follows it."""
# Spec: docs/design/06-project-lifecycle.md §Staging worktree

from boilerplate.composition.staging.finish_steps import FinishSteps
from boilerplate.composition.staging.staging_worktree import StagingWorktree
from boilerplate.models import RestoreKind, RestoreOperation


class Finisher:
    """Run what follows an update's or an add's walk, in the order design 06 gives.

    The copy back brings the walk's result into the user's checkout. A complete
    update or add then runs its tasks and writes its lock and its record. A
    paused update appends its conflict record only. What the lock, the record
    and the tasks are is the operation's own, passed in as callbacks.
    """

    def __init__(
        self, operation: RestoreOperation, kind: RestoreKind, steps: FinishSteps
    ) -> None:
        """Prepare to finish one run.

        Args:
            operation: The command the run belongs to.
            kind: Whether the walk finished every layer or a conflict paused it.
            steps: The operation's lock, record and tasks.
        """
        self._operation = operation
        self._kind = kind
        self._steps = steps

    def copy_back(self, staging: StagingWorktree) -> None:
        """Copy the staging worktree back into the user's checkout.

        Args:
            staging: The active staging of the run.

        Raises:
            UpdateCheckoutChangedError: If the checkout changed during staging.
            UpdatePathObstructedError: If a path the walk added already exists
                in the checkout as a file or directory git ignores.
            UpdateCopyBackFailedError: If the copy back failed after it began
                to write; the checkout is restored to the starting commit.
        """
        staging.copy_back(paused=self._kind is RestoreKind.PAUSED)

    def finish(self) -> bool:
        """Run the operation's steps that follow the copy back.

        Returns:
            Whether the files are kept: ``False`` when a task failed and the
            run was undone.
        """
        steps = self._steps
        if self._kind is RestoreKind.PAUSED:
            steps.write_record()
            return True
        if not steps.run_tasks():
            return False
        steps.write_lock()
        steps.write_record()
        return True
