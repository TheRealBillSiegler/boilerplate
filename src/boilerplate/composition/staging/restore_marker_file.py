"""Keep the restore marker and its ref in the project's git directory."""
# Spec: docs/design/06-project-lifecycle.md §Interrupted copy back

import logging
from pathlib import Path
from typing import Final

from pydantic import ValidationError

from boilerplate.common.exceptions import UpdateInterruptedError
from boilerplate.composition.staging.git_commands import run_git
from boilerplate.models import RestoreMarker
from boilerplate.project_state.atomic_write import write_text_atomically

__all__ = [
    "MARKER_NAME",
    "RESTORE_REF",
    "marker_path",
    "pin_result",
    "read_marker",
    "remove_marker",
    "write_marker",
]

MARKER_NAME: Final = "boilerplate-restore.json"
"""The marker's name inside the git directory of the worktree it belongs to."""

RESTORE_REF: Final = "refs/worktree/boilerplate/restore"
"""The per-worktree ref that keeps the copy back's source commit reachable."""

_logger = logging.getLogger(__name__)


def marker_path(project: Path) -> Path:
    """Return where `project`'s restore marker lives.

    ``git rev-parse --git-path`` resolves under the git directory of the
    worktree the command runs in, so each worktree of a project has its own
    marker, and the file is never part of the tracked tree.

    Args:
        project: The project, a git repository root.

    Returns:
        The marker's path.
    """
    return project / run_git(project, "rev-parse", "--git-path", MARKER_NAME).strip()


def read_marker(project: Path) -> RestoreMarker | None:
    """Read `project`'s restore marker.

    Args:
        project: The project, a git repository root.

    Returns:
        The marker; ``None`` when no run left one.

    Raises:
        UpdateInterruptedError: If the file exists but cannot be read, is not
            UTF-8, or does not parse as a restore marker; the error names the
            file and how to discard it.
    """
    path = marker_path(project)
    try:
        return RestoreMarker.model_validate_json(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError, ValidationError) as error:
        raise UpdateInterruptedError(
            f"An earlier run was cut off while restoring its result into the "
            f"working tree, and its restore marker {path} cannot be read: {error}",
            remediation="Run 'git reset' and then 'git stash --include-untracked' "
            "to set the partial run aside. To discard the marker, delete the file "
            f"and run 'git update-ref -d {RESTORE_REF}'.",
        ) from error


def write_marker(project: Path, marker: RestoreMarker) -> None:
    """Write `marker` for `project`, replacing any marker there in one rename.

    Args:
        project: The project, a git repository root.
        marker: The marker to write.

    Raises:
        OSError: If the file cannot be written; the old marker is untouched.
    """
    write_text_atomically(marker_path(project), marker.model_dump_json(indent=2))
    _logger.debug("Restore marker of %s at phase %s", project, marker.phase)


def pin_result(project: Path, commit: str) -> None:
    """Point the restore ref at `commit`, the copy back's source.

    Args:
        project: The project, a git repository root.
        commit: The commit the copy back restores from.
    """
    run_git(project, "update-ref", RESTORE_REF, commit)


def remove_marker(project: Path) -> None:
    """Remove `project`'s restore marker, then its ref.

    The file goes first, so a crash in between leaves at worst a ref without a
    marker, which the next run removes here too. Either half may be absent.

    Args:
        project: The project, a git repository root.
    """
    marker_path(project).unlink(missing_ok=True)
    run_git(project, "update-ref", "-d", RESTORE_REF)
