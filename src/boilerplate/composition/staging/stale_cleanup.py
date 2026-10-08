"""Remove the staging folders an interrupted run left behind."""

import logging
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import ValidationError

from boilerplate.composition.staging.intent_journal import JOURNAL_NAME, IntentJournal
from boilerplate.composition.staging.staging_removal import remove_staging_folder

_logger = logging.getLogger(__name__)

STAGING_PREFIX = "boilerplate-staging-"
STALE_WINDOW = timedelta(hours=1)


def remove_stale_staging(
    temp_root: Path,
    *,
    now: datetime | None = None,
    window: timedelta = STALE_WINDOW,
) -> tuple[Path, ...]:
    """Remove Boilerplate's own staging folders older than `window`.

    A folder is Boilerplate's own when its name carries the staging prefix and
    it holds a parseable intent journal; the journal's start time sets its age.
    A folder with no journal or an unparseable one is left for the user to
    inspect, as is one owned by another user. For each folder removed, the
    worktree registration is dropped with ``git worktree remove`` and
    ``git worktree prune`` run in the project the journal's ``destination``
    names, which drops the registration of a worktree whose folder is gone.

    Args:
        temp_root: The directory the staging folders were created in.
        now: The time to measure age against; the current time by default.
        window: How old a folder must be before it is stale.

    Returns:
        The folders removed.
    """
    if not temp_root.is_dir():
        return ()
    current = now or datetime.now(UTC)
    removed: list[Path] = []
    for folder in sorted(temp_root.glob(f"{STAGING_PREFIX}*")):
        journal = _stale_journal(folder, current, window)
        if journal is None:
            continue
        project = Path(journal.destination)
        remove_staging_folder(project, folder, folder / project.name)
        if not folder.exists():
            _logger.info("Removed stale staging folder %s", folder)
            removed.append(folder)
    return tuple(removed)


def _stale_journal(
    folder: Path, now: datetime, window: timedelta
) -> IntentJournal | None:
    """Return the journal of `folder` when it is a stale folder of ours."""
    if not (folder / JOURNAL_NAME).is_file():
        return None
    try:
        journal = IntentJournal.read(folder)
    except (ValidationError, OSError):
        _logger.warning("Leaving %s: its journal cannot be read.", folder)
        return None
    if now - journal.started_at <= window:
        return None
    if not _owned_by_current_user(folder):
        _logger.warning("Leaving %s: it belongs to another user.", folder)
        return None
    return journal


def _owned_by_current_user(folder: Path) -> bool:
    """Check the owner of `folder` is the current user (POSIX user id match).

    Windows has no user id to compare; the per-user temp directory is what
    keeps another user's folders out of reach there.
    """
    getuid = getattr(os, "getuid", None)
    if getuid is None:
        return True
    return folder.stat().st_uid == getuid()
