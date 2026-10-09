"""Run the checks an update or an add makes before it reads the working tree."""
# Spec: docs/design/06-project-lifecycle.md §Pre-Flight Check

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from boilerplate.composition.staging.operation_lock import operation_lock
from boilerplate.composition.staging.preflight import require_repository_root
from boilerplate.models import RestoreOperation
from boilerplate.project_state.interrupted_run import require_no_interrupted_run

__all__ = ["preflight"]


@contextmanager
def preflight(
    project: Path, operation: RestoreOperation, *, timeout: float | None = None
) -> Generator[None]:
    """Hold the operation lock over a run, after the checks that come first.

    The checks run in design 06's order: the project is a git repository root
    with a commit, the operation lock is taken, and the restore-marker rules
    run, so no other Boilerplate operation interleaves with them and a cut-off
    run's marker is dealt with before anything reads the working tree. The
    clean-tree and submodule checks (``check_project_ready``) come next, inside
    the block.

    Args:
        project: The project.
        operation: The command that is starting.
        timeout: Seconds to wait for another operation to finish; the value of
            ``BOILERPLATE_LOCK_TIMEOUT`` (default 60) when omitted.

    Yields:
        Nothing; the lock is held for the duration of the block.

    Raises:
        UpdateProjectNotReadyError: If the project is not a git repository root
            with a commit.
        ConcurrencyContentionError: If another operation still holds the lock
            when the timeout passes.
        UpdateInterruptedError: If a cut-off run's marker stops the command.
    """
    require_repository_root(project)
    with operation_lock(project, timeout=timeout):
        require_no_interrupted_run(project, operation)
        yield
