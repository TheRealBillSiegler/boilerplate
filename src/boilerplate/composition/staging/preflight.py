"""Check that a project can be staged before any worktree is created."""

import logging
from pathlib import Path

from boilerplate.common.exceptions import (
    UpdateProjectNotReadyError,
    UpdateSubmodulesUnsupportedError,
)
from boilerplate.composition.staging.git_commands import run_git
from boilerplate.composition.staging.intent_operation import IntentOperation
from boilerplate.integrations.copier_types import ProcessExecutionError

_logger = logging.getLogger(__name__)

_DIRTY_MESSAGE = (
    "Working tree has uncommitted changes. "
    "Commit or stash them before running boilerplate {command}."
)


def check_project_ready(
    project: Path, operation: IntentOperation = IntentOperation.UPDATE
) -> None:
    """Check that `project` is a clean git repository without submodules.

    The tree must have no uncommitted changes, untracked files included:
    Copier refuses to update a project whose ``git status --porcelain`` is not
    empty. A project with submodules is refused too, because git's worktree
    documentation says multiple checkouts of a superproject are not
    recommended.

    Args:
        project: The project folder; it must be the root of its repository.
        operation: The operation that asks, which the dirty-tree message names
            as the command to rerun.

    Raises:
        UpdateProjectNotReadyError: If `project` is not the root of a git
            repository with a commit, or its working tree is dirty.
        UpdateSubmodulesUnsupportedError: If `project` has a ``.gitmodules``
            file; the error names the submodule paths.
    """
    require_repository_root(project)
    if run_git(project, "status", "--porcelain").strip():
        raise UpdateProjectNotReadyError(_DIRTY_MESSAGE.format(command=operation.value))
    if (project / ".gitmodules").is_file():
        paths = _submodule_paths(project)
        raise UpdateSubmodulesUnsupportedError(
            "The project has submodules, which staging does not support: "
            f"{', '.join(paths) or '.gitmodules'}.",
            paths=paths,
        )


def require_repository_root(project: Path) -> None:
    """Check that `project` is the top level of a git repository with a commit.

    Args:
        project: The project folder.

    Raises:
        UpdateProjectNotReadyError: If it is not.
    """
    try:
        top = Path(run_git(project, "rev-parse", "--show-toplevel").strip())
        run_git(project, "rev-parse", "--verify", "HEAD")
    except (ProcessExecutionError, OSError) as error:
        raise UpdateProjectNotReadyError(
            f"'{project}' is not a git repository with at least one commit."
        ) from error
    if not top.samefile(project):
        raise UpdateProjectNotReadyError(
            f"'{project}' is not the root of its git repository ('{top}')."
        )


def _submodule_paths(project: Path) -> tuple[str, ...]:
    """Return the paths ``.gitmodules`` declares, in file order."""
    try:
        listing = run_git(
            project,
            "config",
            "--file",
            ".gitmodules",
            "--get-regexp",
            r"^submodule\..*\.path$",
        )
    except ProcessExecutionError:
        _logger.warning("Could not read submodule paths from .gitmodules.")
        return ()
    return tuple(
        line.split(" ", 1)[1].strip() for line in listing.splitlines() if " " in line
    )
