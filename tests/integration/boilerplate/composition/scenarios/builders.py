"""Project builders and project-state readers shared by the composition scenarios.

Most scenarios run on the made-up template family: ``compose_family`` composes
a project from chosen tags of its layers and points each layer's answers file at
its repository, and ``update_family_layer`` updates one layer between two sets
of tags through the harness in ``tests.boilerplate.templates.conftest``. The
scenarios whose claims the family cannot express build releases of the bundled
layers instead (``build_releases``, ``build_repos``). Everything a scenario
writes lives under pytest's temp directory, Copier's own temp copies included
(``temp_dir_inside`` in ``tests.integration.boilerplate.composition.temp_dir``).
"""

import contextlib
import shutil
from collections.abc import Callable, Generator, Mapping, Sequence
from pathlib import Path
from typing import Any, NamedTuple, TypedDict, Unpack

import pytest
import yaml

from boilerplate.composition.updating import ScopedWorker, render_role
from boilerplate.composition.views import LayerView
from tests.boilerplate.templates.conftest import (
    TEMPLATES,
    build_layer_repo,
    commit_all,
    compose_project,
    copy_layer_into,
    git,
    init_repo,
    rehome_layer,
    update_layer,
)
from tests.integration.boilerplate.composition.family import (
    Family,
    assemble_templates_dir,
)

ANSWERS: dict[str, Any] = {
    "project_name": "Probe App",
    "description": "Probe description",
    "author_name": "Ada Probe",
    "author_email": "ada@example.com",
    "container_registry": "ghcr.io",
}
FAMILY_PROJECT = "Family App"
AUTHOR = "Ada Probe"
USER_LINE = "USER LINE: keep me across updates."
EXTENSIONS_DIR = Path(__file__).parent / "extensions"

# The bundled questionnaire the scenarios were written against: `project`
# declares every shared question, `streamlit` only its own and its overrides.
PROJECT_QUESTIONS = frozenset(
    {
        "project_name",
        "project_slug",
        "package_name",
        "description",
        "dependencies",
        "dev_dependencies",
        "sample_module",
        "author_name",
        "author_email",
        "package_index_url",
    }
)
STREAMLIT_OWN_QUESTIONS = frozenset(
    {"dependencies", "sample_module", "container_registry"}
)
# The answers a `project` answers file records: hidden questions are not.
PROJECT_RECORDED = PROJECT_QUESTIONS - {"project_slug", "package_name"}

Mutator = Callable[[str, Path], None]


def require(condition: bool, message: str) -> None:
    """Fail the scenario at setup when the templates no longer match it.

    Args:
        condition: Whether the precondition holds.
        message: What the scenario expected of the templates.
    """
    if not condition:
        pytest.fail(
            f"Scenario precondition failed: {message}. The bundled templates "
            "changed, so this scenario no longer applies as written; revise it "
            "before reading its verdict.",
            pytrace=False,
        )


@contextlib.contextmanager
def extensions_on_path() -> Generator[None]:
    """Make the probe-only extension modules importable while the block runs."""
    with pytest.MonkeyPatch.context() as patch:
        patch.syspath_prepend(str(EXTENSIONS_DIR))
        yield


def write(path: Path, text: str) -> None:
    """Write `text` to `path` with LF line endings, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def append(path: Path, text: str) -> None:
    """Append `text` to the file at `path`."""
    write(path, path.read_text(encoding="utf-8") + text)


def substitute(path: Path, old: str, new: str) -> None:
    """Replace the first `old` in the file at `path` with `new`.

    Args:
        path: The template file to edit.
        old: Text the scenario expects the file to contain.
        new: Its replacement.
    """
    text = path.read_text(encoding="utf-8")
    require(old in text, f"{path.name} contains {old!r}")
    write(path, text.replace(old, new, 1))


def read_yaml(path: Path) -> dict[str, Any]:
    """Return the mapping a YAML file holds; an empty file yields ``{}``."""
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def declared_questions(config_path: Path) -> frozenset[str]:
    """Return the question names a ``copier.yml`` declares (directives excluded)."""
    config = read_yaml(config_path)
    return frozenset(str(k) for k in config if not str(k).startswith("_"))


def check_bundled_questionnaire() -> None:
    """Fail unless the bundled layers declare the questions the scenarios assume."""
    require(
        declared_questions(TEMPLATES / "project" / "copier.yml") == PROJECT_QUESTIONS,
        f"project/copier.yml declares exactly {sorted(PROJECT_QUESTIONS)}",
    )
    require(
        declared_questions(TEMPLATES / "streamlit" / "copier.yml")
        == STREAMLIT_OWN_QUESTIONS,
        "streamlit/copier.yml declares only its own questions and overrides, "
        f"{sorted(STREAMLIT_OWN_QUESTIONS)}",
    )


def build_releases(
    root: Path,
    refs: Sequence[str],
    mutate: Mutator | None = None,
    *,
    merge_readme: bool = True,
) -> dict[str, Path]:
    """Write one templates directory per ref holding both bundled layers.

    Args:
        root: The scenario's working directory.
        refs: The release refs, oldest first.
        mutate: Called as ``mutate(ref, release_dir)`` to make each release
            differ; it may add synthetic layers beside the bundled ones.
        merge_readme: Whether to drop ``README.md`` from both layers'
            ``_skip_if_exists``, so an update merges into the README.

    Returns:
        Each release's templates directory, keyed by ref.
    """
    check_bundled_questionnaire()
    releases: dict[str, Path] = {}
    for ref in refs:
        release = root / "releases" / ref
        for layer in ("project", "streamlit"):
            copy_layer_into(TEMPLATES / layer, release / layer)
            if merge_readme:
                substitute(release / layer / "copier.yml", '  - "README.md"\n', "")
        if mutate is not None:
            mutate(ref, release)
        releases[ref] = release
    return releases


def build_repos(
    root: Path,
    releases: Mapping[str, Path],
    tags: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, Path]:
    """Turn every layer of `releases` into a git repository tagged per release.

    Args:
        root: The scenario's working directory.
        releases: Each release's templates directory, keyed by ref.
        tags: The refs to tag for a layer, keyed by layer name; a layer not
            named gets every ref.

    Returns:
        Each layer's repository, keyed by layer name.
    """
    first = next(iter(releases.values()))
    repos: dict[str, Path] = {}
    for layer in sorted(p.name for p in first.iterdir() if p.is_dir()):
        refs = (tags or {}).get(layer, list(releases))
        repos[layer] = build_layer_repo(
            root / "repos" / layer, {ref: releases[ref] / layer for ref in refs}
        )
    return repos


def make_git_project(
    project: Path, repos: Mapping[str, Path], tags: str | Mapping[str, str]
) -> None:
    """Point every layer `project` records at its repository, then commit.

    Args:
        project: The composed project.
        repos: Each layer's repository, keyed by layer name.
        tags: The tag each layer's render matches, keyed by layer name; a
            single tag stands for every layer, for releases that share one
            tag across layers.
    """
    for layer, repo in repos.items():
        if (project / f".copier-answers.{layer}.yml").exists():
            tag = tags if isinstance(tags, str) else tags[layer]
            rehome_layer(project, layer=layer, source=repo, commit=tag)
    init_repo(project)
    label = (
        tags
        if isinstance(tags, str)
        else ", ".join(f"{k} {v}" for k, v in tags.items())
    )
    commit_all(project, f"compose {label}")


def templates_at(family: Family, work: Path, tags: Mapping[str, str]) -> Path:
    """Return a templates directory holding each layer of `tags` at its tag.

    A directory is built once per combination of tags and reused.

    Args:
        family: The built family.
        work: The scenario's working directory.
        tags: The tag of each layer to include, keyed by layer name.

    Returns:
        The templates directory.
    """
    name = "-".join(f"{layer[:2]}{tag}" for layer, tag in sorted(tags.items()))
    templates = work / "templates" / name
    if not templates.exists():
        assemble_templates_dir(family, templates, tags)
    return templates


class UpdateOptions(TypedDict, total=False):
    """The ``update_layer`` options a scenario may set."""

    full_view: bool
    step_views: bool
    ask_unanswered: bool
    data: Mapping[str, Any] | None
    skip_tasks: bool
    quiet: bool
    interactive: bool
    skip_answered: bool
    worker_type: type[ScopedWorker]


def compose_family(
    family: Family,
    work: Path,
    root: str,
    tags: Mapping[str, str],
    answers: Mapping[str, Any] | None = None,
    *,
    skip_tasks: bool = True,
) -> Path:
    """Compose `root` and its ancestors at `tags` into a git-backed project.

    Args:
        family: The built family.
        work: The scenario's working directory.
        root: The composition's final layer.
        tags: The tag of each layer in the composition, keyed by layer name.
        answers: Answers forced beside the project name.
        skip_tasks: Whether to skip the merged post-generation tasks.

    Returns:
        The project, committed with each layer pointing at its repository.
    """
    templates = templates_at(family, work, tags)
    project = work / "composed" / "family-app"
    compose_project(
        root,
        project,
        {"project_name": FAMILY_PROJECT, **(answers or {})},
        templates,
        skip_tasks=skip_tasks,
    )
    make_git_project(project, family.repos, tags)
    return project


def update_family_layer(
    family: Family,
    project: Path,
    *,
    root: str,
    layer: str,
    before: Mapping[str, str],
    after: Mapping[str, str],
    work: Path,
    **options: Unpack[UpdateOptions],
) -> None:
    """Update one layer of a family project from its tag in `before` to `after`.

    The old copy renders under the view of the templates at `before`, the new
    copy and the project in place under the view at `after`: the layer's scoped
    view, the root's full view or an update step's view, as the options ask.

    Args:
        family: The built family.
        project: The composed, git-backed project.
        root: The composition's final layer.
        layer: The layer to update.
        before: Every composed layer's tag at the recorded release.
        after: Every composed layer's tag at the target release.
        work: The scenario's working directory.
        **options: Passed on to ``update_layer``.
    """
    new = after[layer]
    update_layer(
        project,
        root=root,
        layer=layer,
        source=family.repos[layer],
        ref=new,
        templates={new: templates_at(family, work, after)},
        old_templates=templates_at(family, work, before),
        **options,
    )


def copy_project(base: Path, dest: Path) -> Path:
    """Copy the composed project `base` to `dest` and return `dest`."""
    shutil.copytree(base, dest)
    return dest


def add_user_line(path: Path, *, prepend: bool = False) -> None:
    """Add ``USER_LINE`` to the project file at `path` and commit it.

    Args:
        path: A file inside a git-backed project.
        prepend: Whether to add the line at the top instead of the end.
    """
    text = path.read_text(encoding="utf-8")
    write(path, f"{USER_LINE}\n{text}" if prepend else f"{text}\n{USER_LINE}\n")
    commit_all(_project_root(path), "user edit")


def _project_root(path: Path) -> Path:
    return Path(git(path.parent, "rev-parse", "--show-toplevel").strip())


def answers_file(project: Path, layer: str) -> dict[str, Any]:
    """Return everything `layer`'s answers file records, Copier's keys included."""
    return read_yaml(project / f".copier-answers.{layer}.yml")


def lines(path: Path) -> list[str]:
    """Return the lines of the text file at `path`."""
    return path.read_text(encoding="utf-8").splitlines()


def tree(root: Path) -> dict[str, str]:
    """Return every file under `root` outside ``.git``, keyed by POSIX path."""
    return {
        p.relative_to(root).as_posix(): p.read_text(encoding="utf-8", errors="replace")
        for p in sorted(root.rglob("*"))
        if p.is_file() and ".git" not in p.relative_to(root).parts
    }


class MergeState(NamedTuple):
    """What an update left for the user to resolve.

    Attributes:
        marked: Files holding conflict markers.
        rejects: ``.rej`` files left beside their targets.
        unmerged: Paths git reports as unmerged.
    """

    marked: list[str]
    rejects: list[str]
    unmerged: list[str]


CLEAN = MergeState([], [], [])


def merge_state(project: Path) -> MergeState:
    """Return the conflicts an update left in `project`."""
    files = tree(project)
    unmerged = git(project, "ls-files", "-u").splitlines()
    return MergeState(
        sorted(p for p, text in files.items() if "<<<<<<< " in text),
        sorted(p for p in files if p.endswith(".rej")),
        sorted({line.split("\t", 1)[1] for line in unmerged}),
    )


class Recording(NamedTuple):
    """What a ``recording_worker`` saw during an update.

    Attributes:
        builds: ``(role, ref)`` for every template a worker built, in order;
            role is ``old_copy``, ``new_copy`` or ``in_place``.
        copies: The watched files' contents after each render of the update,
            keyed by role (``old_copy``, ``in_place`` or ``new_copy``), then by
            file; ``None`` for a file not rendered.
        views: ``(role, view)`` for every template a worker built, in order:
            the view the render drew its template from.
    """

    builds: list[tuple[str, str | None]]
    copies: dict[str, dict[str, str | None]]
    views: list[tuple[str, LayerView]]


def _role(worker: ScopedWorker) -> str:
    return render_role(Path(str(worker.dst_path))).value


def recording_worker(
    files: Sequence[str] = (), base: type[ScopedWorker] = ScopedWorker
) -> tuple[type[ScopedWorker], Recording]:
    """Return a subclass of `base` that records what each render did.

    Args:
        files: Project-relative files to read once each render finishes.
        base: The worker class to record, a ``ScopedWorker`` unless a scenario
            compares another view choice.

    Returns:
        The worker class to pass to ``update_layer`` and the recording it
        fills.
    """
    recording = Recording([], {}, [])

    class RecordingWorker(base):
        """Record each template build and the watched files of each copy."""

        def view_for_render(self) -> LayerView:
            """Record the build, then return the view this render draws from."""
            view = super().view_for_render()
            recording.builds.append((_role(self), self.resolved_vcs_ref))
            recording.views.append((_role(self), view))
            return view

        def run_copy(self) -> None:
            """Render, then read the watched files out of the destination."""
            super().run_copy()
            dst = Path(str(self.dst_path))
            recording.copies[_role(self)] = {
                f: (dst / f).read_text(encoding="utf-8") if (dst / f).exists() else None
                for f in files
            }

    return RecordingWorker, recording


def by_ref_worker(recorded_ref: str, target_ref: str) -> type[ScopedWorker]:
    """Return a worker that keys its views by template ref, as the first design did.

    It looks the view up by the ref Copier sets on the render, in a mapping
    from the recorded ref to the old view and the target ref to the target
    view. When only an ancestor moves the two refs are the same string, the
    target view overwrites the old one in the mapping, and every render
    draws from it.

    Args:
        recorded_ref: The layer's ref at the recorded release.
        target_ref: The layer's ref at the target release.

    Returns:
        The worker class to pass to ``update_family_layer``.
    """

    class ByRefWorker(ScopedWorker):
        """Draw each render's view from a mapping keyed by template ref."""

        def view_for_render(self) -> LayerView:
            """Return the view keyed by the ref this render sets."""
            views = {recorded_ref: self.old_view, target_ref: self.target_view}
            assert self.resolved_vcs_ref is not None
            return views[self.resolved_vcs_ref]

    return ByRefWorker


# Scenario S10c: project v4 adds a `license` question its files render, and
# streamlit v4 overrides its default.
LICENSE_QUESTION = (
    '\nlicense:\n  type: str\n  help: "License identifier for the project."\n'
    '  default: "MIT"\n'
)
LICENSE_OVERRIDE = (
    '\n# Override project\'s `license` default.\nlicense:\n  default: "Apache-2.0"\n'
)
LICENSE_FILE = "project_license.txt"


def license_releases(ref: str, release: Path) -> None:
    """Add project's `license` question at v4 and override its default in streamlit."""
    project, streamlit = release / "project", release / "streamlit"
    if ref == "v4":
        append(project / "copier.yml", LICENSE_QUESTION)
        write(project / f"{LICENSE_FILE}.jinja", "license={{ license }}\nrelease=v4\n")
        append(streamlit / "copier.yml", LICENSE_OVERRIDE)


def on_own_worker(value: object, name: str) -> object:
    """Return a fixture param whose tests all run on one xdist worker.

    A module-scoped fixture is built once per worker that runs a test using
    it; grouping the tests of one param keeps that to one build.

    Args:
        value: The param's value.
        name: The param's id, also its xdist group.

    Returns:
        A ``pytest.param`` carrying the group mark.
    """
    return pytest.param(value, id=name, marks=pytest.mark.xdist_group(name))
