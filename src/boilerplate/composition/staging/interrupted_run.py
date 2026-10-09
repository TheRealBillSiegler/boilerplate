"""Apply the restore-marker rules to a run that was cut off after its walk."""
# Spec: docs/design/06-project-lifecycle.md §Interrupted copy back

import logging
from collections.abc import Iterator, Sequence
from pathlib import Path

from boilerplate.common.exceptions import UpdateInterruptedError
from boilerplate.composition.staging.committed_lock import read_committed_lock
from boilerplate.composition.staging.git_commands import run_git
from boilerplate.composition.staging.restore_marker_file import (
    read_marker,
    remove_marker,
)
from boilerplate.integrations.copier_types import ProcessExecutionError
from boilerplate.models import (
    MigrationRecord,
    MigrationStatus,
    RestoreKind,
    RestoreMarker,
    RestoreOperation,
    RestorePhase,
)
from boilerplate.project_state.migrations_file import read_migrations

__all__ = ["resolve_interrupted_run"]

_logger = logging.getLogger(__name__)

_SET_ASIDE = (
    "Run 'git reset' and then 'git stash --include-untracked' to set the "
    "partial run aside, then run the command again."
)


def resolve_interrupted_run(
    project: Path, operation: RestoreOperation
) -> RestoreMarker | None:
    """Apply the restore-marker rules before an update or an add plans anything.

    Call it inside the operation lock and before anything reads the working
    tree, which a cut-off run may have left dirty. The first rule that matches
    decides. With no marker, a ref left without one is removed. A marker whose
    run appended its record since it began, or one that no longer binds
    because the working tree is clean, is removed, and the command goes on as
    a fresh run. A marker of another command, or of a run whose HEAD has
    moved, stops the command. Otherwise the cut-off run can be finished: a run
    cut off in its tasks or as it recorded always can, and one cut off in its
    copy back can when it was complete and every path that differs from the
    starting commit matches the result commit.

    Args:
        project: The project, a git repository root.
        operation: The command that is starting.

    Returns:
        The marker of the run to finish; ``None`` to go on as a fresh run.

    Raises:
        UpdateInterruptedError: If the marker belongs to another command, HEAD
            moved since the run began, or a copy back was cut off that cannot
            be repeated; the error names the run's targets. Also if the marker
            does not parse.
        LockReadFailedError: If a cut-off update's starting commit holds no
            lock that parses, so its last layer cannot be told.
    """
    marker = read_marker(project)
    if marker is None:
        remove_marker(project)
        return None
    if _run_finished(project, marker, read_migrations(project)):
        remove_marker(project)
        return None
    if not run_git(project, "status", "--porcelain").strip():
        _logger.warning(
            "Removed the restore marker of an earlier run (moving to %s): the "
            "working tree is clean, so it was set aside or committed.",
            _named(marker),
        )
        remove_marker(project)
        return None
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
    if marker.phase is not RestorePhase.COPY_BACK:
        return marker
    if marker.kind is RestoreKind.PAUSED:
        raise _stop(
            marker,
            " A conflict had paused it, and its conflicted files cannot be "
            "restored again.",
        )
    if not _matches_result(project, marker.result_commit):
        raise _stop(
            marker,
            " Your working tree differs from its result: edited since, or left "
            "half written.",
        )
    return marker


def _run_finished(
    project: Path, marker: RestoreMarker, records: Sequence[MigrationRecord]
) -> bool:
    """Check whether the log's last record is the marked run's own.

    A ``conflict`` record matches on its targets; any other record matches when
    it names the walk's last layer at its target.
    """
    if not records or records[-1].timestamp <= marker.started_at:
        return False
    last = records[-1]
    if last.status is MigrationStatus.CONFLICT:
        return dict(last.targets or {}) == dict(marker.targets)
    layer = _last_layer(project, marker)
    version = marker.targets.get(layer)
    return version is not None and last.to_version == f"{layer}@{version}"


def _last_layer(project: Path, marker: RestoreMarker) -> str:
    """Name the marked walk's last layer: the added one, or the update's root.

    An update walks the lock's layers in order, root last, so the root is read
    from the lock at the run's starting commit rather than from the order the
    marker's targets were written in.
    """
    if marker.operation is RestoreOperation.ADD:
        (added,) = marker.targets
        return added
    return read_committed_lock(project, marker.start_commit).layers[-1].name


def _matches_result(project: Path, result_commit: str) -> bool:
    """Check that every path that differs from HEAD matches `result_commit`.

    The comparison goes through git, so line-ending and filter settings apply
    as they do to the copy back: a tracked path is compared with ``git diff
    --quiet``, and an added one by its ``git hash-object`` against the blob
    the result commit holds.
    """
    for code, path in _changed_paths(project):
        if code == "??":
            if not _added_matches(project, result_commit, path):
                return False
        elif not _tracked_matches(project, result_commit, path):
            return False
    return True


def _changed_paths(project: Path) -> Iterator[tuple[str, str]]:
    """Yield the status code and path of each entry ``git status`` lists."""
    listing = run_git(
        project, "status", "--porcelain=v1", "-z", "--untracked-files=all"
    )
    entries = iter(listing.split("\0"))
    for entry in entries:
        if not entry:
            continue
        code, path = entry[:2], entry[3:]
        if code[0] in "RC":
            next(entries, None)
        yield code, path


def _tracked_matches(project: Path, result_commit: str, path: str) -> bool:
    """Check whether the tracked `path` matches `result_commit`, deletion included."""
    try:
        run_git(project, "diff", "--quiet", result_commit, "--", f":(literal){path}")
    except ProcessExecutionError:
        return False
    return True


def _added_matches(project: Path, result_commit: str, path: str) -> bool:
    """Check whether the untracked `path` is the blob `result_commit` holds."""
    try:
        expected = run_git(project, "rev-parse", f"{result_commit}:{path}").strip()
        found = run_git(project, "hash-object", "--", path).strip()
    except ProcessExecutionError:
        return False
    return found == expected


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
