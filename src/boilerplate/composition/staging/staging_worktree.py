"""A detached git worktree of a project, in which an update or an add runs."""

import logging
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Self

from boilerplate.composition.staging.git_commands import run_git
from boilerplate.composition.staging.intent_journal import IntentJournal
from boilerplate.composition.staging.intent_operation import IntentOperation
from boilerplate.composition.staging.preflight import check_project_ready
from boilerplate.composition.staging.staging_removal import remove_staging_folder

_logger = logging.getLogger(__name__)

STAGING_PREFIX = "boilerplate-staging-"


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
            operation: The operation the staging belongs to.
            template_ref: The template reference of the operation, if any.
            temp_root: The directory to create the unique folder in; the
                system temp directory when omitted.
        """
        self.project = project
        self.operation = operation
        self.template_ref = template_ref
        self._temp_root = temp_root
        self._folder: Path | None = None
        self._start_commit: str | None = None

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

    def __enter__(self) -> Self:
        """Check the project, then create the worktree and its journal.

        Returns:
            The active staging.

        Raises:
            UpdateProjectNotReadyError: If the project is dirty or not a
                repository root.
            UpdateSubmodulesUnsupportedError: If the project has submodules.
        """
        check_project_ready(self.project)
        root = self._temp_root or Path(tempfile.gettempdir())
        self._folder = Path(tempfile.mkdtemp(prefix=STAGING_PREFIX, dir=root))
        try:
            self._start_commit = run_git(self.project, "rev-parse", "HEAD").strip()
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

    def _write_journal(self, phase: str) -> None:
        """Write the journal beside the worktree with `phase`."""
        IntentJournal(
            operation=self.operation,
            phase=phase,
            started_at=datetime.now(UTC),
            staging_dir=str(self.folder),
            destination=str(self.project),
            template_ref=self.template_ref,
        ).write(self.folder)

    def _discard(self) -> None:
        """Remove the worktree and the unique folder."""
        if self._folder is None:
            return
        folder, self._folder = self._folder, None
        remove_staging_folder(self.project, folder, folder / self.project.name)
