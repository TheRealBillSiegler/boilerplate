"""Apply the restore-marker rules to a run that was cut off after its walk."""
# Spec: docs/design/06-project-lifecycle.md §Interrupted copy back

import logging
from collections.abc import Sequence
from pathlib import Path

from boilerplate.common.exceptions import UpdateInterruptedError
from boilerplate.composition.staging.git_commands import run_git
from boilerplate.composition.staging.restore_marker_file import (
    read_marker,
    remove_marker,
)
from boilerplate.models import (
    MigrationRecord,
    MigrationStatus,
    RestoreMarker,
    RestoreOperation,
)
from boilerplate.project_state.migrations_file import read_migrations

__all__ = ["require_no_interrupted_run"]

_logger = logging.getLogger(__name__)

_SET_ASIDE = (
    "Run 'git reset' and then 'git stash --include-untracked' to set the "
    "partial run aside, then run the command again."
)


def require_no_interrupted_run(project: Path, operation: RestoreOperation) -> None:
    """Apply the restore-marker rules before an update or an add plans anything.

    Call it inside the operation lock and before anything reads the working
    tree, which a cut-off run may have left dirty. With no marker, a ref left
    without one is removed. A marker whose run appended its record since it
    began, or one that no longer binds because the working tree is clean, is
    removed and the command goes on as a fresh run.

    Args:
        project: The project, a git repository root.
        operation: The command that is starting.

    Raises:
        UpdateInterruptedError: If the marker belongs to another command, HEAD
            moved since the run began, or the working tree still holds what the
            cut-off run left; the error names the run's targets. Also if the
            marker does not parse.
    """
    marker = read_marker(project)
    if marker is None:
        remove_marker(project)
        return
    if _run_finished(marker, read_migrations(project)):
        remove_marker(project)
        return
    if not run_git(project, "status", "--porcelain").strip():
        _logger.warning(
            "Removed the restore marker of an earlier run (moving to %s): the "
            "working tree is clean, so it was set aside or committed.",
            _named(marker),
        )
        remove_marker(project)
        return
    if marker.operation is not operation:
        raise _stop(
            marker,
            "",
            remediation=f"Run 'boilerplate {marker.operation}' to finish it, or run "
            "'git reset' and then 'git stash --include-untracked' to set it aside "
            "and run the command again.",
        )
    if run_git(project, "rev-parse", "HEAD").strip() != marker.start_commit:
        raise _stop(marker, " HEAD has moved since it began.")
    raise _stop(marker, " Its changes are in your working tree.")


def _run_finished(marker: RestoreMarker, records: Sequence[MigrationRecord]) -> bool:
    """Check whether the log's last record is the marked run's own.

    A ``conflict`` record matches on its targets; any other record matches when
    it names the walk's last layer at its target.
    """
    if not records or records[-1].timestamp <= marker.started_at:
        return False
    last = records[-1]
    if last.status is MigrationStatus.CONFLICT:
        return dict(last.targets or {}) == dict(marker.targets)
    layer, version = list(marker.targets.items())[-1]
    return last.to_version == f"{layer}@{version}"


def _named(marker: RestoreMarker) -> str:
    """Name the marked run's targets, ``layer@version`` each."""
    return ", ".join(f"{layer}@{version}" for layer, version in marker.targets.items())


def _stop(
    marker: RestoreMarker, reason: str, *, remediation: str = _SET_ASIDE
) -> UpdateInterruptedError:
    """Build the stop for the marked run, with `reason` after the common message."""
    return UpdateInterruptedError(
        f"An earlier 'boilerplate {marker.operation}' was cut off while restoring "
        f"its result into the working tree (moving to {_named(marker)}).{reason}",
        targets=marker.targets,
        remediation=remediation,
    )
