"""The order the shared finisher runs an operation's steps in.

Design 06 §Staging worktree: a complete update runs its tasks, then writes the
lock and appends the record; §Add pipeline: an add runs its tasks, then writes the
lock and appends the record; §Step 5: a paused update appends its conflict
record and writes no lock.
"""

import pytest

from boilerplate.composition.staging.finish_steps import FinishSteps
from boilerplate.composition.staging.finisher import Finisher
from boilerplate.models import RestoreKind, RestoreOperation


def recording_steps(calls: list[str], *, keep: bool = True) -> FinishSteps:
    """Build steps that note each call; the tasks keep the files or undo."""

    def run_tasks() -> bool:
        calls.append("tasks")
        return keep

    return FinishSteps(
        write_record=lambda: calls.append("record"),
        write_lock=lambda: calls.append("lock"),
        run_tasks=run_tasks,
    )


class TestFinishOrder:
    @pytest.mark.parametrize(
        ("operation", "kind", "order"),
        [
            pytest.param(
                RestoreOperation.UPDATE,
                RestoreKind.COMPLETE,
                ["tasks", "lock", "record"],
                id="update",
            ),
            pytest.param(
                RestoreOperation.ADD,
                RestoreKind.COMPLETE,
                ["tasks", "lock", "record"],
                id="add",
            ),
            pytest.param(
                RestoreOperation.UPDATE, RestoreKind.PAUSED, ["record"], id="paused"
            ),
        ],
    )
    def test_runs_the_steps_in_design_order(
        self, operation: RestoreOperation, kind: RestoreKind, order: list[str]
    ) -> None:
        """Run each operation's steps in the order design 06 gives."""
        calls: list[str] = []

        Finisher(operation, kind, recording_steps(calls)).finish()

        assert calls == order

    def test_an_undone_update_writes_no_lock_and_no_record(self) -> None:
        """Stop after the tasks when they undo the update."""
        calls: list[str] = []

        kept = Finisher(
            RestoreOperation.UPDATE,
            RestoreKind.COMPLETE,
            recording_steps(calls, keep=False),
        ).finish()

        assert (kept, calls) == (False, ["tasks"])
