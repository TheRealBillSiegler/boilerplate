"""Shared rendering and git helpers for the bundled-template test modules.

Every module under this package renders one of the bundled layers through the
real composition and rendering pipeline (no mocked Copier Worker) and then
asserts on the output, or drives vanilla ``copier update`` against a tagged
git checkout of one. Centralizing the layer-discovery glob, the
``ExecutionContext`` wiring, and the git-repo-building helpers here keeps them
from drifting across modules that render or update the same templates.
"""

import shutil
import subprocess
from pathlib import Path

import boilerplate
from boilerplate.cli.utils import build_template_catalog
from boilerplate.composition import Composer
from boilerplate.composition.rendering.engine import RenderEngine
from boilerplate.composition.rendering.models.execution_context import (
    ExecutionContext,
)
from boilerplate.composition.resolution import Resolver
from boilerplate.settings import Settings

TEMPLATES = Path(boilerplate.__file__).parent / "templates"
LAYERS = sorted(p.parent for p in TEMPLATES.glob("*/copier.yml"))


def render(
    name: str,
    tmp_path: Path,
    *,
    context_data: dict[str, object] | None = None,
    profile: dict[str, object] | None = None,
    skip_tasks: bool = True,
) -> Path:
    """Render the bundled layer `name` into `tmp_path / "out"` with the given answers.

    Args:
        name: Layer name, e.g. "project" or "streamlit".
        tmp_path: Pytest's per-test temp directory; the layer renders into its
            `out` subdirectory.
        context_data: Copier's forced `data` channel: values taken as-is and
            never prompted.
        profile: Copier's overridable `user_defaults` channel: pre-fills
            interactive prompts, overridden by an interactive answer or a
            forced `context_data` value.
        skip_tasks: Whether to skip post-generation tasks (`--no-tasks`).

    Returns:
        The rendered project's destination directory.
    """
    registry = build_template_catalog(None, Settings())
    resolution = Resolver().resolve(name, registry)
    composition = Composer().compose(resolution)
    dest = tmp_path / "out"
    ctx = ExecutionContext(
        destination=dest,
        context_data=context_data or {},
        profile=profile or {},
        overwrite=True,
        interactive=False,
        skip_tasks=skip_tasks,
    )
    RenderEngine().render(composition, ctx)
    return dest


def git(repo: Path, *args: str) -> str:
    """Run a git command in `repo` with a fixed test identity, returning stdout.

    Args:
        repo: The git working tree to run in.
        args: Arguments passed to the ``git`` executable.

    Returns:
        The command's stdout.
    """
    return subprocess.run(
        ["git", "-c", "user.name=tests", "-c", "user.email=tests@example.com", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout


def commit_all(repo: Path, message: str, tag: str | None = None) -> None:
    """Stage and commit every change in `repo`, optionally tagging the commit.

    Args:
        repo: The git working tree to commit in.
        message: The commit message.
        tag: A tag name to apply to the new commit, or `None` for no tag.
    """
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)
    if tag:
        git(repo, "tag", tag)


def copy_layer_into(layer: Path, repo: Path) -> None:
    """Copy a bundled layer's tree into `repo`, ready for `git init`.

    Args:
        layer: The bundled layer directory to copy.
        repo: The destination directory (need not exist yet).
    """
    shutil.copytree(
        layer, repo, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__")
    )
