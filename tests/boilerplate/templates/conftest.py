"""Shared rendering, update and git helpers for the bundled-template test modules.

Every module under this package renders one of the bundled layers through the
real composition and rendering pipeline (no mocked Copier Worker) and then
asserts on the output, or composes a project and updates one of its layers
against a tagged git checkout of that layer. Centralizing the layer-discovery
glob, the ``ExecutionContext`` wiring, the compose and update harness and the
git-repo-building helpers here keeps them from drifting across modules that
render or update the same templates.

Two views of a composition drive a layer's render:

- The *full* view is the whole composition's merged questionnaire and
  extension union, which ``RenderEngine`` gives every layer (``render``).
- The *scoped* view of a layer is the merged questionnaire and extension
  union of that layer and its ancestors only (``layer_view``). The harness
  composes a project by asking the full questionnaire once and rendering each
  layer under its scoped view (``compose_project``), and updates one layer
  through ``ScopedWorker``, which renders every copy Copier's update makes
  under the scoped view of the ref that copy renders at (``update_layer``).

The view builder, ``ScopedWorker``, the update answer rule and the single-layer
update are Boilerplate's own code in ``boilerplate.composition.views`` and
``boilerplate.composition.updating``; the helpers here resolve and compose, read
answers files and call them. The composition scenarios reuse this harness.
"""

import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any, NamedTuple

import boilerplate
from boilerplate.cli.utils import build_template_catalog
from boilerplate.composition import Composer
from boilerplate.composition.models.composition import Composition
from boilerplate.composition.rendering.engine import (
    _WORKER_EXCLUDES,  # pyright: ignore[reportPrivateUsage]
    RenderEngine,
)
from boilerplate.composition.rendering.models.execution_context import (
    ExecutionContext,
)
from boilerplate.composition.rendering.models.merged_template import MergedTemplate
from boilerplate.composition.resolution import Resolver
from boilerplate.composition.tasks import normalize_tasks
from boilerplate.composition.updating import (
    LayerRelease,
    ScopedWorker,
    StepInputs,
    UpdateOptions,
    UpdateViews,
    read_recorded_answers,
    read_recorded_answers_by_layer,
)
from boilerplate.composition.updating import update_layer as update_layer_in_src
from boilerplate.composition.views import (
    LayerView,
    build_layer_view,
    build_step_view,
    registered_ancestor_extensions,
    view_config,
)
from boilerplate.integrations.copier_types import (
    Template,
    Worker,
    load_answersfile_data,
)
from boilerplate.settings import Settings

TEMPLATES = Path(boilerplate.__file__).parent / "templates"
LAYERS = sorted(p.parent for p in TEMPLATES.glob("*/copier.yml"))


def compose(name: str, templates_dir: Path | None = None) -> Composition:
    """Resolve and compose layer `name`, searching `templates_dir` first."""
    registry = build_template_catalog(templates_dir, Settings())
    return Composer().compose(Resolver().resolve(name, registry))


def render_full_view(
    name: str,
    dest: Path,
    *,
    context_data: Mapping[str, object] | None = None,
    profile: Mapping[str, object] | None = None,
    skip_tasks: bool = True,
    templates_dir: Path | None = None,
) -> Path:
    """Render the composition rooted at `name` into `dest` through ``RenderEngine``.

    ``RenderEngine`` renders every layer under the composition's full view,
    which is what ``boilerplate new`` does.

    Args:
        name: The composition's root layer, e.g. "project" or "streamlit".
        dest: The destination directory.
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
    ctx = ExecutionContext(
        destination=dest,
        context_data=dict(context_data or {}),
        profile=dict(profile or {}),
        overwrite=True,
        interactive=False,
        skip_tasks=skip_tasks,
    )
    RenderEngine().render(compose(name, templates_dir), ctx)
    return dest


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
    return render_full_view(
        name,
        tmp_path / "out",
        context_data=context_data,
        profile=profile,
        skip_tasks=skip_tasks,
        templates_dir=templates_dir,
    )


def layer_view(name: str, templates_dir: Path | None = None) -> LayerView:
    """Return the merged view of the composition rooted at layer `name`.

    Rooted at a layer, the composition holds that layer and its ancestors, so
    this is the layer's scoped view; rooted at the composition's final layer,
    it is the full view.

    Args:
        name: The layer to compose.
        templates_dir: An extra directory searched ahead of the bundled
            templates.

    Returns:
        The merged questions and importable extension union.
    """
    return build_layer_view(compose(name, templates_dir))


def step_view(layer: str, root: str, templates_dir: Path | None = None) -> LayerView:
    """Return the view an update step of `layer` renders under.

    The scoped view's questions under the full view's definitions: `layer`'s
    composition for the scope, `root`'s for the definitions.

    Args:
        layer: The layer being updated.
        root: The composition's final layer.
        templates_dir: An extra directory searched ahead of the bundled
            templates.

    Returns:
        The step's view.
    """
    return build_step_view(compose(layer, templates_dir), compose(root, templates_dir))


def layer_chain(name: str, templates_dir: Path | None = None) -> list[str]:
    """Return `name`'s ancestors in topological order, `name` itself last."""
    return [layer.name for layer in compose(name, templates_dir).layers]


def _primed_worker(template: Template, **options: object) -> Worker:
    """Return a Worker whose `template` is `template`, cleanup registered."""
    worker = Worker(**options)  # pyright: ignore[reportCallIssue]
    object.__setattr__(worker, "template", template)
    worker._cleanup_hooks.append(template._cleanup)  # pyright: ignore[reportPrivateUsage]
    return worker


class QuestionnaireAnswers(NamedTuple):
    """The answers one questionnaire pass produced.

    Attributes:
        user: Every question's answer, hidden (``when: false``) ones included.
        metadata: Copier's own ``_``-prefixed answers.
        hidden: Names of the questions that were never shown.
    """

    user: dict[str, Any]
    metadata: dict[str, Any]
    hidden: frozenset[str]


def ask_merged_questionnaire(
    root: str,
    data: Mapping[str, Any],
    templates_dir: Path | None = None,
    *,
    defaults: bool = True,
) -> QuestionnaireAnswers:
    """Run one questionnaire pass over the full merged view of `root`.

    The first layer's Worker asks the merged questionnaire, the way
    ``RenderEngine`` does, into a scratch destination that is discarded.

    Args:
        root: The composition's root layer.
        data: Copier's forced `data` channel for the pass.
        templates_dir: An extra directory searched ahead of the bundled
            templates.
        defaults: Whether to accept every default instead of prompting.

    Returns:
        The pass's answers.
    """
    composition = compose(root, templates_dir)
    view = layer_view(root, templates_dir)
    first = composition.layers[0]
    template = MergedTemplate(
        str(first.path), dict(view.questions), view_config(view, skip_if_exists=[])
    )
    with (
        tempfile.TemporaryDirectory() as scratch,
        _primed_worker(
            template,
            src_path=str(first.path),
            dst_path=Path(scratch),
            data=dict(data),
            user_defaults={},
            defaults=defaults,
            unsafe=True,
            quiet=True,
        ) as worker,
        registered_ancestor_extensions(view.ancestor_extensions),
    ):
        worker._ask()  # pyright: ignore[reportPrivateUsage]
        return QuestionnaireAnswers(
            dict(worker.answers.user),
            dict(worker.answers.metadata),
            frozenset(worker.answers.hidden),
        )


def compose_project(
    root: str,
    dest: Path,
    answers: Mapping[str, Any],
    templates_dir: Path | None = None,
    *,
    skip_tasks: bool = True,
    register_ancestors: bool = True,
) -> dict[str, Any]:
    """Compose the project rooted at `root` into `dest` under scoped views.

    One questionnaire pass over the full merged view answers every question;
    each layer then renders, in topological order, under its own scoped view
    with those answers pre-seeded, so it records only the answers its scoped
    view asks. The merged tasks run once, on the final layer.

    Args:
        root: The composition's root layer.
        dest: The destination directory.
        answers: Answers forced into the questionnaire pass.
        templates_dir: An extra directory searched ahead of the bundled
            templates.
        skip_tasks: Whether to skip the merged post-generation tasks.
        register_ancestors: Whether each layer's render loads the file-path
            extensions its ancestors declare, as ``ScopedWorker`` does for an
            update; off, a layer using an ancestor's filter fails to render.

    Returns:
        The questionnaire pass's public answers.
    """
    composition = compose(root, templates_dir)
    asked = ask_merged_questionnaire(root, answers, templates_dir)
    seeded = {**asked.user, **asked.metadata}
    tasks = normalize_tasks(composition.final)
    for index, layer in enumerate(composition.layers):
        run_tasks = (
            index == len(composition.layers) - 1 and not skip_tasks and bool(tasks)
        )
        view = layer_view(layer.name, templates_dir)
        if not register_ancestors:
            view = view._replace(ancestor_extensions=())
        config = view_config(view, skip_if_exists=[])
        if run_tasks:
            config["tasks"] = tasks
        template = MergedTemplate(str(layer.path), dict(view.questions), config)
        with (
            _primed_worker(
                template,
                src_path=str(layer.path),
                dst_path=dest,
                data=dict(seeded),
                user_defaults={},
                unsafe=True,
                overwrite=True,
                defaults=True,
                skip_tasks=not run_tasks,
                exclude=_WORKER_EXCLUDES,
                quiet=True,
            ) as worker,
            registered_ancestor_extensions(view.ancestor_extensions),
        ):
            worker.run_copy()
    return {k: v for k, v in seeded.items() if not k.startswith("_")}


def recorded_answers(project: Path, layer: str) -> dict[str, Any]:
    """Return the public answers `layer`'s answers file records in `project`."""
    return read_recorded_answers(project, layer)


def force_recorded_answers(
    project: Path,
    *,
    layer: str,
    templates_dir: Path | None = None,
    full_view: bool = False,
) -> dict[str, Any]:
    """Return the answers the rule an update step replaced forced as data.

    The recorded answers of `layer`'s chain, ancestors first and the layer's own
    on top, which outrank the layer's own answers file in Copier. An update step
    no longer passes them; a scenario forces them to show what that did.

    Args:
        project: The composed project.
        layer: The layer being updated.
        templates_dir: The templates directory holding the target release.
        full_view: Whether to merge every answers file, in file-name order,
            instead of `layer`'s chain.

    Returns:
        The merged recorded answers.
    """
    recorded_by_layer = read_recorded_answers_by_layer(project)
    chain = list(recorded_by_layer) if full_view else layer_chain(layer, templates_dir)
    merged: dict[str, Any] = {}
    for name in chain:
        merged.update(recorded_by_layer.get(name, {}))
    return merged


def _recorded_ref(project: Path, layer: str) -> str:
    """Return the ref `project`'s answers file records for `layer`."""
    recorded = load_answersfile_data(project, Path(f".copier-answers.{layer}.yml"))
    return str(recorded["_commit"])


def update_layer(
    project: Path,
    *,
    root: str,
    layer: str,
    source: Path,
    ref: str,
    templates: Mapping[str, Path | None],
    full_view: bool = False,
    step_views: bool = False,
    data: Mapping[str, Any] | None = None,
    force_recorded: bool = False,
    secrets: Mapping[str, Any] | None = None,
    old_templates: Path | None = None,
    old_view: LayerView | None = None,
    target_view: LayerView | None = None,
    skip_tasks: bool = True,
    quiet: bool = True,
    interactive: bool = False,
    skip_answered: bool = False,
    worker_type: type[ScopedWorker] = ScopedWorker,
) -> dict[str, Any]:
    """Update one layer of a composed project to `ref` under two views.

    Args:
        project: The composed project, a git repository with a clean tree.
        root: The composition's root layer.
        layer: The layer to update; names its `.copier-answers.<layer>.yml`.
        source: The layer's git-backed template source.
        ref: The git ref of the target template version.
        templates: The templates directory holding each release a render of
            this update reads, keyed by ref (`None` for the bundled
            templates); the project's recorded ref and `ref` must both be
            keys, unless `old_templates` stands in for the recorded one.
        full_view: Whether to render under the root's full view, as
            ``RenderEngine`` would, instead of `layer`'s scoped view.
        step_views: Whether to build the views as an update step does, the
            layer's scope under the full schema's definitions, instead of
            `layer`'s scoped view or, with `full_view`, the root's full view.
        data: Values supplied to the step, as data for the questions in the
            layer's scope; ``{}`` supplies none.
        force_recorded: Whether to supply the recorded answers of `layer`'s
            chain too, own on top (``force_recorded_answers``): the rule the
            step replaced, to show what it did.
        secrets: Secret answers given earlier in the same update.
        old_templates: The directory the old copy's view is composed from,
            for an update whose layer keeps its ref while an ancestor moves,
            so `templates` cannot hold both; by default `templates` at the
            ref the project records for `layer`.
        old_view: The view the old copy renders under instead of composing
            it from the old templates.
        target_view: The view the in-place render and the new copy render
            under instead of composing it from `templates` at `ref`.
        skip_tasks: Whether to skip the layer's own post-generation tasks.
        quiet: Whether to silence Copier's progress output.
        interactive: Whether the step prompts for the layer's own questions.
        skip_answered: Whether the step asks only unanswered questions.
        worker_type: The worker class to update with.

    Returns:
        The secret answers the step ended with.
    """
    view_root = root if full_view else layer

    def view_at(templates_dir: Path | None) -> LayerView:
        if step_views:
            return step_view(layer, root, templates_dir)
        return layer_view(view_root, templates_dir)

    if old_view is None:
        if old_templates is None:
            old_templates = templates[_recorded_ref(project, layer)]
        old_view = view_at(old_templates)
    if target_view is None:
        target_view = view_at(templates[ref])
    supplied = dict(data or {})
    if force_recorded:
        supplied = {
            **force_recorded_answers(
                project,
                layer=layer,
                templates_dir=templates[ref],
                full_view=full_view,
            ),
            **supplied,
        }
    return update_layer_in_src(
        project,
        LayerRelease(layer=layer, source=source, ref=ref),
        UpdateViews(old_view, target_view),
        inputs=StepInputs(supplied=supplied, secrets=secrets or {}),
        options=UpdateOptions(
            skip_tasks=skip_tasks,
            quiet=quiet,
            interactive=interactive,
            skip_answered=skip_answered,
            worker_type=worker_type,
        ),
    )


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
        elif not line.startswith("_commit:"):
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
    git(repo, "commit", "-q", "--allow-empty", "-m", message)
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


def build_layer_repo(repo: Path, releases: Mapping[str, Path]) -> Path:
    """Build a git history in `repo` with one tagged commit per release.

    Args:
        repo: The directory to initialize (need not exist yet).
        releases: Each release's layer directory, keyed by its tag, in
            release order.

    Returns:
        The git working tree, tagged at every release.
    """
    repo.mkdir(parents=True, exist_ok=True)
    init_repo(repo)
    for tag, layer in releases.items():
        for child in repo.iterdir():
            if child.name != ".git":
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
        copy_layer_into(layer, repo)
        # Same-size edits inside one mtime tick can hide from git's stat
        # cache; dropping the index makes `add` rehash every file.
        git(repo, "rm", "-r", "-q", "--cached", "--ignore-unmatch", ".")
        commit_all(repo, f"release {tag}", tag)
    return repo
