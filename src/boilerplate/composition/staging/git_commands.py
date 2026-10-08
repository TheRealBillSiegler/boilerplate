"""Run git for the staging worktree, through the command Copier runs its own with."""

import logging
import os
from pathlib import Path

from plumbum.commands.processes import ProcessExecutionError

from boilerplate.integrations.copier_types import get_git

_logger = logging.getLogger(__name__)

__all__ = ["ProcessExecutionError", "run_git"]


def run_git(cwd: Path, *args: str, stdin: str | None = None) -> str:
    """Run one git command in `cwd` with the repository's hooks disabled.

    Copier runs its own git calls with ``core.hooksPath`` pointing at the null
    device where a hook would interfere; the staging worktree does the same for
    every call, so no hook of the user's repository fires during staging.

    Args:
        cwd: The directory to run in; git's ``-C`` is set to it.
        args: The git subcommand and its arguments.
        stdin: Text to feed the command's standard input, if any.

    Returns:
        The command's standard output.

    Raises:
        ProcessExecutionError: If git exits non-zero.
    """
    command = get_git(cwd)["-c", f"core.hooksPath={os.devnull}", *args]
    _logger.debug("git -C %s %s", cwd, " ".join(args))
    if stdin is not None:
        return (command << stdin)()
    return command()
