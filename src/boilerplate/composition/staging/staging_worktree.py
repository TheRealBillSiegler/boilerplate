"""A detached git worktree of a project, in which an update or an add runs."""

import logging
import tempfile
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Self

from boilerplate.common.file_lock import FileLock
from boilerplate.composition.staging.copy_back import (
    list_untracked_paths,
    require_checkout_unchanged,
    restore_working_tree,
    undo_working_tree,
)
from boilerplate.composition.staging.git_commands import run_git
from boilerplate.composition.staging.intent_journal import (
    JOURNAL_LOCK_NAME,
    IntentJournal,
)
from boilerplate.composition.staging.intent_operation import IntentOperation
from boilerplate.composition.staging.layer_commit import commit_worktree
from boilerplate.composition.staging.path_obstruction import (
    list_added_paths,
    list_uncommitted_paths,
    require_paths_unobstructed,
)
from boilerplate.composition.staging.preflight import check_project_ready
from boilerplate.composition.staging.staging_removal import remove_staging_folder
from boilerplate.composition.staging.stale_cleanup import (
    STAGING_PREFIX,
    remove_stale_staging,
)
from boilerplate.composition.staging.unmerged_entries import (
    list_unmerged_paths,
    replay_unmerged_entries,
)
from boilerplate.composition.staging.working_tree_changes import (
    apply_working_tree_changes,
)

_logger = logging.getLogger(__name__)


class StagingWorktree:
    """A detached worktree of a project, removed whenever its block exits.

    The worktree lives in a uniquely named folder under the system temp
    directory, and its own folder name is the project's, so Copier's
    ``_folder_name`` resolves to the same value as in the user's checkout. The
    intent journal sits in the unique folder beside the worktree, never inside
    it. The user's checkout changes only when a copy back is requested.

    Attributes:
        project: The user's checkout.
        operation: The operation the staging belongs to.
        template_ref: The template reference of the operation, if any.
    """

    def __init__(
        self,
        project: Path,
        *,
        operation: IntentOperation,
        template_ref: str | None = None,
        temp_root: Path | None = None,
    ) -> None:
        """Prepare a staging of `project`; nothing is created until entry.

        Args:
            project: The project to stage; the root of a clean git repository.
                A relative path is resolved against the current directory now,
                so the worktree's name and the journal's destination do not
                depend on the directory of whichever process reads them later.
            operation: The operation the staging belongs to.
            template_ref: The template reference of the operation, if any.
            temp_root: The directory to create the unique folder in; the
                system temp directory when omitted.
        """
        self.project = project.resolve()
        self.operation = operation
        self.template_ref = template_ref
        self._temp_root = temp_root
        self._folder: Path | None = None
        self._lock: FileLock | None = None
        self._start_commit: str | None = None
        self._last_commit: str | None = None
        self._started_at = datetime.now(UTC)

    @property
    def folder(self) -> Path:
        """The uniquely named folder holding the worktree and the journal."""
        if self._folder is None:
            raise RuntimeError("The staging worktree is not active.")
        return self._folder

    @property
    def path(self) -> Path:
        """The worktree, named like the project folder."""
        return self.folder / self.project.name

    @property
    def start_commit(self) -> str:
        """The commit the user's checkout was at when staging began."""
        if self._start_commit is None:
            raise RuntimeError("The staging worktree is not active.")
        return self._start_commit

    @property
    def last_commit(self) -> str:
        """The worktree's newest layer commit, or the start commit before any."""
        if self._last_commit is None:
            raise RuntimeError("The staging worktree is not active.")
        return self._last_commit

    def commit_layer(self, message: str) -> str:
        """Commit everything in the worktree with git's plumbing.

        Args:
            message: The commit message.

        Returns:
            The new commit; the worktree is clean afterwards.
        """
        self._last_commit = commit_worktree(self.path, message)
        return self._last_commit

    def unmerged_paths(self) -> tuple[str, ...]:
        """List the worktree's unmerged paths, the sign a layer's update conflicted.

        Returns:
            The conflicted paths; empty when the layer's update merged cleanly.
        """
        return list_unmerged_paths(self.path)

    def record_phase(self, phase: str) -> None:
        """Write the intent journal with `phase`.

        The walk names the phases a project operation passes through: the
        worktree itself writes ``staging`` and ``committing``, and the caller
        writes ``locking`` before it writes the lock.

        Args:
            phase: The phase to record.
        """
        self._write_journal(phase)

    def untracked_in_checkout(self) -> tuple[str, ...]:
        """List the files the user's checkout has that git neither tracks nor ignores.

        After a copy back these are the files the update added, and the files a
        task wrote; listing them is what lets ``undo_copy_back`` remove exactly
        those.

        Returns:
            The paths relative to the checkout.
        """
        return list_untracked_paths(self.project)

    def undo_copy_back(self, untracked: Sequence[str]) -> None:
        """Return the user's checkout to the state it had when staging began.

        Tracked files are restored from the starting commit, working tree and
        index both, and the listed files are removed.

        Args:
            untracked: The files to remove, as ``untracked_in_checkout`` listed
                them after the copy back and the tasks.
        """
        undo_working_tree(self.project, self.start_commit, untracked)

    def copy_back(self, *, paused: bool = False) -> None:
        """Reproduce the worktree's state in the user's checkout.

        The checkout must still be at the starting commit with no changes. Its
        files then match the last layer commit, additions and deletions both,
        as uncommitted, unstaged changes, the way plain Copier leaves them.

        A paused copy back is for a walk that stopped on a layer whose update
        left conflicts. That layer is not committed, so after the restore the
        worktree's remaining working-tree changes are applied, and its
        unmerged index entries are replayed into the checkout's index; the
        conflicted files then show as unmerged and ``git commit`` refuses them.

        Args:
            paused: Whether the last layer paused on a conflict.

        Raises:
            UpdateCheckoutChangedError: If the checkout changed during staging;
                it is left as it is.
            UpdatePathObstructedError: If a path the walk added already exists
                in the checkout as a file or directory git ignores; nothing is
                written.
        """
        require_checkout_unchanged(self.project, self.start_commit, self.operation)
        added = list_added_paths(self.project, self.start_commit, self.last_commit)
        if paused:
            added = (*added, *list_uncommitted_paths(self.path))
        require_paths_unobstructed(self.project, added)
        self.record_phase("committing")
        restore_working_tree(self.project, self.last_commit)
        if paused:
            apply_working_tree_changes(self.path, self.project)
            replay_unmerged_entries(self.path, self.project)

    def __enter__(self) -> Self:
        """Check the project, then create the worktree and its journal.

        Returns:
            The active staging.

        Raises:
            UpdateProjectNotReadyError: If the project is dirty or not a
                repository root.
            UpdateSubmodulesUnsupportedError: If the project has submodules.
        """
        check_project_ready(self.project, self.operation)
        self._started_at = datetime.now(UTC)
        root = self._temp_root or Path(tempfile.gettempdir())
        remove_stale_staging(root)
        self._folder = Path(tempfile.mkdtemp(prefix=STAGING_PREFIX, dir=root))
        try:
            self._hold_lock()
            self._start_commit = run_git(self.project, "rev-parse", "HEAD").strip()
            self._last_commit = self._start_commit
            self._write_journal("staging")
            run_git(self.project, "worktree", "add", "--detach", str(self.path), "HEAD")
        except BaseException:
            self._discard()
            raise
        _logger.debug("Staging worktree created at %s", self.path)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Remove the worktree and its folder, whether or not the block failed."""
        self._discard()

    def _hold_lock(self) -> None:
        """Take the exclusive lock that marks this staging as live.

        The lock is taken before the journal is written, so the stale cleanup
        never sees a journal whose operation is not yet holding it.

        Raises:
            RuntimeError: If another process holds the lock of this brand-new
                folder, which nothing else can know the name of.
        """
        lock = FileLock(self.folder / JOURNAL_LOCK_NAME)
        if not lock.try_acquire():
            raise RuntimeError(f"Could not lock the new staging folder {self.folder}.")
        self._lock = lock

    def _write_journal(self, phase: str) -> None:
        """Write the journal beside the worktree with `phase`."""
        IntentJournal(
            operation=self.operation,
            phase=phase,
            started_at=self._started_at,
            staging_dir=str(self.folder),
            destination=str(self.project),
            template_ref=self.template_ref,
        ).write(self.folder)

    def _discard(self) -> None:
        """Remove the worktree and the unique folder."""
        if self._folder is None:
            return
        folder, self._folder = self._folder, None
        self._last_commit = None
        if self._lock is not None:
            self._lock.release()
            self._lock = None
        remove_staging_folder(self.project, folder, folder / self.project.name)
