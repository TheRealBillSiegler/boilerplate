"""The intent journal of a staged operation."""

import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict

from boilerplate.composition.staging.intent_operation import IntentOperation

JOURNAL_NAME = ".boilerplate-commit-intent.json"
JOURNAL_LOCK_NAME = ".boilerplate-commit-intent.lock"


class IntentJournal(BaseModel):
    """The in-progress state of a mutating operation, kept for crash recovery.

    It is written before the operation begins and deleted with the staging
    folder on completion. For a staging worktree it sits in the staging
    folder beside the worktree, so ``git add -A`` in the worktree never picks
    it up. The running operation holds an exclusive lock on the file
    ``JOURNAL_LOCK_NAME`` beside it for its whole lifetime, which is how the
    stale cleanup tells a live operation from a dead one. The journal itself is
    replaced by rename on every write, which a lock on it would block on
    Windows, so the lock sits on its own file.

    Attributes:
        operation: The operation that owns the journal.
        phase: The current phase; ``staging``, ``committing`` or ``locking``
            for project operations.
        started_at: When the operation began.
        staging_dir: The staging folder that holds the journal.
        destination: The project the operation changes.
        template_ref: The template reference of a create, update or add.
    """

    model_config = ConfigDict(frozen=True)

    operation: IntentOperation
    phase: str
    started_at: datetime
    staging_dir: str
    destination: str
    template_ref: str | None = None

    def write(self, folder: Path) -> None:
        """Write the journal into `folder` atomically.

        The text goes to a sibling temporary file that is then renamed over the
        journal, so a crash never leaves a truncated journal.

        Args:
            folder: The staging folder to write into.
        """
        handle, temporary = tempfile.mkstemp(dir=folder, prefix=f"{JOURNAL_NAME}.tmp.")
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(self.model_dump_json(indent=2))
            Path(temporary).replace(folder / JOURNAL_NAME)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise

    @classmethod
    def read(cls, folder: Path) -> Self:
        """Read the journal in `folder`.

        Args:
            folder: The staging folder that holds the journal.

        Returns:
            The journal.

        Raises:
            pydantic.ValidationError: If the file is not a valid journal.
            OSError: If the file cannot be read.
        """
        # Bytes, not text: pydantic decodes them itself, so a file that is not
        # UTF-8 fails validation instead of raising UnicodeDecodeError here.
        return cls.model_validate_json((folder / JOURNAL_NAME).read_bytes())
