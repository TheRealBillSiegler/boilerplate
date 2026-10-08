"""A task that failed after the update's files were copied back."""

import shlex
from typing import Self

from pydantic import BaseModel, ConfigDict

from boilerplate.integrations.copier_types import TaskError


class FailedTask(BaseModel):
    """What the user needs to know about a failed task.

    Attributes:
        command: The task's command as Copier ran it, quoted so it can be pasted.
        returncode: The command's exit status.
        rerun: How to run the task by hand.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    command: str
    returncode: int
    rerun: str

    @classmethod
    def from_error(cls, error: TaskError) -> Self:
        """Describe the task Copier's task runner stopped on.

        Args:
            error: The error the task runner raised.

        Returns:
            The failed task.
        """
        command = error.cmd if isinstance(error.cmd, str) else shlex.join(error.cmd)
        return cls(
            command=command,
            returncode=error.returncode,
            rerun=f"Run it by hand from the project root: {command}",
        )
