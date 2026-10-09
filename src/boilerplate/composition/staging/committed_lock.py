"""Read the lock a project had at one of its commits."""
# Spec: docs/design/06-project-lifecycle.md §Interrupted copy back

from pathlib import Path

from boilerplate.common.exceptions import LockReadFailedError
from boilerplate.composition.staging.git_commands import run_git
from boilerplate.integrations.copier_types import ProcessExecutionError
from boilerplate.models import BoilerplateLock
from boilerplate.project_state.lock_file import LOCK_FILE_NAME, parse_lock

__all__ = ["read_committed_lock"]


def read_committed_lock(project: Path, commit: str) -> BoilerplateLock:
    """Read ``boilerplate.lock`` as `commit` holds it.

    A run cut off after its walk may already have written the new lock, so
    finishing it reads the lock it started from out of its starting commit.

    Args:
        project: The project, a git repository root.
        commit: The commit to read the lock from.

    Returns:
        The lock at `commit`.

    Raises:
        LockReadFailedError: If `commit` holds no lock, or one that does not
            parse.
        LockSchemaUnsupportedError: If that lock's schema major is newer than
            this tool supports.
    """
    try:
        text = run_git(project, "show", f"{commit}:{LOCK_FILE_NAME}")
    except ProcessExecutionError as error:
        raise LockReadFailedError(
            f"{LOCK_FILE_NAME} not found in commit {commit}."
        ) from error
    return parse_lock(text)
