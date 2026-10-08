"""Staging: a detached git worktree an update or an add runs in."""

from boilerplate.composition.staging.intent_journal import JOURNAL_NAME, IntentJournal
from boilerplate.composition.staging.intent_operation import IntentOperation
from boilerplate.composition.staging.preflight import check_project_ready
from boilerplate.composition.staging.staging_worktree import StagingWorktree
from boilerplate.composition.staging.stale_cleanup import (
    STALE_WINDOW,
    remove_stale_staging,
)

__all__ = [
    "JOURNAL_NAME",
    "STALE_WINDOW",
    "IntentJournal",
    "IntentOperation",
    "StagingWorktree",
    "check_project_ready",
    "remove_stale_staging",
]
