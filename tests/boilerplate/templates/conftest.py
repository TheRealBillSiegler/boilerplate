"""Shared rendering, update and git helpers for the bundled-template test modules.

Every module under this package renders one of the bundled layers through the
real composition and rendering pipeline (no mocked Copier Worker) and then
asserts on the output, or updates one layer of a composed project through the
composition's merged view against a tagged git checkout of that layer.
Centralizing the layer-discovery glob, the ``ExecutionContext`` wiring, the
update harness and the git-repo-building helpers here keeps them from drifting
across modules that render or update the same templates.
"""

import shutil
import subprocess
from dataclasses import field
from functools import cached_property
from pathlib import Path
from typing import Any

import yaml
from pydantic import ConfigDict
from pydantic.dataclasses import dataclass

import boilerplate
from boilerplate.cli.utils import build_template_catalog
from boilerplate.composition import Composer
from boilerplate.composition.models.composition import Composition
from boilerplate.composition.rendering.engine import RenderEngine
from boilerplate.composition.rendering.models.execution_context import (
    ExecutionContext,
)
from boilerplate.composition.rendering.models.merged_template import MergedTemplate
from boilerplate.composition.resolution import Resolver
from boilerplate.integrations.copier_types import Template, Worker
from boilerplate.settings import Settings

TEMPLATES = Path(boilerplate.__file__).parent / "templates"
LAYERS = sorted(p.parent for p in TEMPLATES.glob("*/copier.yml"))


def compose(name: str, templates_dir: Path | None = None) -> Composition:
    """Resolve and compose layer `name`, searching `templates_dir` first."""
    registry = build_template_catalog(templates_dir, Settings())
    return Composer().compose(Resolver().resolve(name, registry))


def render(
    name: str,
    tmp_path: Path,
    *,
    context_data: dict[str, object] | None = None,
    profile: dict[str, object] | None = None,
    skip_tasks: bool = True,
    templates_dir: Path | None = None,
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
        templates_dir: An extra directory searched ahead of the bundled
            templates, the way `--templates-dir` is; a layer there shadows a
            bundled layer of the same name and version.

    Returns:
        The rendered project's destination directory.
    """
    composition = compose(name, templates_dir)
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


def _merged_view(name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return the merged questions and extension union of the composition at `name`."""
    composition = compose(name)
    raw = composition.final.get("_jinja_extensions")
    # Filepath-style specs resolve inside the declaring layer's own tree, so
    # they stay layer-local; module-path specs travel to every layer.
    extensions = (
        [str(e) for e in raw if not str(e).split(":", 1)[0].endswith(".py")]
        if isinstance(raw, list)
        else []
    )
    config: dict[str, Any] = {"jinja_extensions": extensions} if extensions else {}
    return dict(composition.merged_questions_schema), config


@dataclass(config=ConfigDict(extra="forbid"))
class ComposedWorker(Worker):  # pyright: ignore[reportUntypedBaseClass, reportGeneralTypeIssues]
    """A Copier Worker that renders its layer from the composition's merged view.

    Copier's update rebuilds its old-copy and new-copy workers with
    ``dataclasses.replace``, so a template primed on one worker instance never
    reaches those renders. A merged view held in fields of the class travels
    with ``replace`` into every render an update performs; each layer then
    answers the whole questionnaire while writing only its own files, which is
    design 04's update walk (Safe Update). It is the test harness for
    per-layer updates of the bundled templates.
    """

    merged_questions: dict[str, Any] = field(default_factory=dict)
    merged_config: dict[str, Any] = field(default_factory=dict)

    @cached_property
    def template(self) -> Template:  # pyright: ignore[reportIncompatibleVariableOverride]
        url = self.src_path
        if not url:
            assert self.subproject.template is not None
            url = str(self.subproject.template.url)
        result = MergedTemplate(
            url,
            dict(self.merged_questions),
            dict(self.merged_config) or None,
            ref=self.resolved_vcs_ref,
        )
        self._cleanup_hooks.append(result._cleanup)  # pyright: ignore[reportPrivateUsage]
        return result


def update_layer(
    project: Path,
    *,
    root: str,
    layer: str,
    source: Path,
    ref: str,
) -> None:
    """Update one layer of a composed project to `ref` through the merged view.

    Args:
        project: The composed project, a git repository with a clean tree.
        root: The composition's root template, whose graph gives the merged view.
        layer: The layer to update; names its `.copier-answers.<layer>.yml`.
        source: The layer's git-backed template source.
        ref: The git ref of the target template version.
    """
    questions, config = _merged_view(root)
    answers: dict[str, Any] = {}
    for answers_file in sorted(project.glob(".copier-answers.*.yml")):
        recorded = yaml.safe_load(answers_file.read_text(encoding="utf-8")) or {}
        answers.update(
            {k: v for k, v in recorded.items() if not str(k).startswith("_")}
        )
    with ComposedWorker(  # pyright: ignore[reportCallIssue, reportGeneralTypeIssues]
        src_path=str(source),
        dst_path=project,
        answers_file=f".copier-answers.{layer}.yml",
        data=answers,
        vcs_ref=ref,
        defaults=True,
        overwrite=True,
        quiet=True,
        unsafe=True,
        skip_tasks=True,
        merged_questions=questions,
        merged_config=config,
    ) as worker:
        worker.run_update()


def rehome_layer(project: Path, *, layer: str, source: Path, commit: str) -> None:
    """Point a composed project's `layer` at the git-backed `source` at `commit`.

    A plain-directory render records only ``_src_path`` in the layer's answers
    file; rehoming the layer to a git source is the one-line edit ADR-015
    point 5 documents, with the tag the directory's content matches.

    Args:
        project: The composed project.
        layer: The layer whose `.copier-answers.<layer>.yml` to rewrite.
        source: The layer's git-backed template source.
        commit: The tag or commit in `source` whose content the render matches.
    """
    answers_path = project / f".copier-answers.{layer}.yml"
    rehomed: list[str] = []
    for line in answers_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("_src_path:"):
            rehomed.append(f"_commit: {commit}")
            rehomed.append(f"_src_path: {source.as_posix()}")
        else:
            rehomed.append(line)
    answers_path.write_text("\n".join(rehomed) + "\n", encoding="utf-8")


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


def init_repo(repo: Path) -> None:
    """Initialize a git repo in `repo` on `main` with long paths enabled (Windows)."""
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "core.longpaths", "true")


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
    """Copy a layer's tree into `repo`, ready for `git init`.

    Args:
        layer: The layer directory to copy.
        repo: The destination directory (need not exist yet).
    """
    shutil.copytree(
        layer, repo, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__")
    )
