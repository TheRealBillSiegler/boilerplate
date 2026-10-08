"""How a layer's render can load a file-path Jinja extension another layer ships.

``copier_template_extensions`` resolves a file-path spec (``path.py:Class``)
against the rendering template's own root, so a descendant cannot name an
ancestor's file directly. D17 probes which spellings of another template's
file resolve, from a local directory and from Copier's git clone. S19
registers the ancestor's file as an importable module per release, so a
descendant renders with the ancestor's extension at the release each copy of
an update renders. It runs on the made-up template family: docs 1.2.0 changes
what its filter returns, and app's file shows it.
"""

import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path, PurePath
from typing import NamedTuple

import pytest
from jinja2.exceptions import TemplateAssertionError

from boilerplate.composition.rendering.scoped_worker import ScopedWorker
from tests.boilerplate.templates.conftest import (
    commit_all,
    compose_project,
    init_repo,
    render_full_view,
)
from tests.integration.boilerplate.composition.family import Family
from tests.integration.boilerplate.composition.scenarios.builders import (
    ANSWERS,
    CLEAN,
    FAMILY_PROJECT,
    USER_LINE,
    add_user_line,
    build_releases,
    build_repos,
    by_ref_worker,
    compose_family,
    lines,
    make_git_project,
    merge_state,
    recording_worker,
    substitute,
    templates_at,
    update_family_layer,
    write,
)
from tests.integration.boilerplate.composition.temp_dir import temp_dir_inside

LOADER = "copier_template_extensions.TemplateExtensionLoader"
FIRST_RELEASES = {"core": "1.0.0", "service": "1.0.0", "docs": "1.0.0", "app": "1.0.0"}

# ------------------------------------------------------------------ D17

CONTEXT_HOOK = """from copier_template_extensions import ContextHook


class ContextUpdater(ContextHook):
    def hook(self, context):
        context["probe_value"] = "from A"
"""
ON_WINDOWS = sys.platform == "win32"
# Copier's own API in a fresh interpreter: pytest's import hooks would turn the
# loader's first `__import__` attempt on a path into a ValueError the loader
# does not catch, where a plain interpreter raises ImportError and the loader
# falls back to the file path, as in a standalone run.
RENDER = (
    "import sys\n"
    "from copier import run_copy\n"
    "run_copy(sys.argv[1], sys.argv[2], defaults=True, overwrite=True,\n"
    "         unsafe=True, quiet=True, vcs_ref=sys.argv[3] or None)\n"
)
UNRESOLVED = (
    "copier.errors.UserMessageError: Could not resolve path to local extension module"
)


class Rendered(NamedTuple):
    """The outcome of rendering a D17 template.

    Attributes:
        output: The rendered `out.txt`, or `None` when the render failed.
        stderr: The interpreter's stderr.
    """

    output: str | None
    stderr: str


def _template(path: Path, spec: str) -> Path:
    """Write a template rendering `probe_value` with `spec` loaded."""
    write(path / "copier.yml", f"_jinja_extensions:\n  - {LOADER}\n  - '{spec}'\n")
    write(path / "out.txt.jinja", "{{ probe_value }}")
    return path


def _render(template: Path, dest: Path) -> Rendered:
    """Render `template` in a fresh interpreter, from a git clone if it is a repo."""
    ref = "HEAD" if (template / ".git").exists() else ""
    result = subprocess.run(
        [sys.executable, "-c", RENDER, str(template), str(dest), ref],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    out = dest / "out.txt"
    output = out.read_text(encoding="utf-8") if result.returncode == 0 else None
    return Rendered(output, result.stderr)


def _as_repo(template: Path) -> Path:
    init_repo(template)
    commit_all(template, "template", "v1.0.0")
    return template


class Spellings(NamedTuple):
    """Template A's extension file, spelled the ways another template could name it."""

    walk_out: str
    drive_absolute_posix: str
    drive_absolute_native: str
    driveless_posix: str
    driveless_native: str
    drive_letter: str


@pytest.fixture()
def template_a(tmp_path: Path) -> Spellings:
    """Write template A, whose own spec loads its context hook."""
    a = _template(tmp_path / "A", "extensions/context.py:ContextUpdater")
    hook = a / "extensions" / "context.py"
    write(hook, CONTEXT_HOOK)
    driveless = PurePath(str(hook)[len(hook.drive) :])
    return Spellings(
        walk_out="../A/extensions/context.py:ContextUpdater",
        drive_absolute_posix=f"{hook.as_posix()}:ContextUpdater",
        drive_absolute_native=f"{hook}:ContextUpdater",
        driveless_posix=f"{driveless.as_posix()}:ContextUpdater",
        driveless_native=f"{driveless}:ContextUpdater",
        drive_letter=hook.drive[:1],
    )


class TestFilePathSpellings:
    """D17: which spellings of another template's extension file resolve."""

    @pytest.mark.usefixtures("template_a")
    def test_own_relative_spec_loads(self, tmp_path: Path) -> None:
        """D17: a template's own relative spec resolves against its root."""
        assert _render(tmp_path / "A", tmp_path / "out").output == "from A"

    def test_walk_out_relative_spec_loads_from_a_local_directory(
        self, template_a: Spellings, tmp_path: Path
    ) -> None:
        """D17: `../A/...` resolves while B renders from its own directory."""
        b = _template(tmp_path / "B", template_a.walk_out)

        assert _render(b, tmp_path / "out").output == "from A"

    def test_walk_out_relative_spec_fails_from_a_git_clone(
        self, template_a: Spellings, tmp_path: Path
    ) -> None:
        """D17: from Copier's temp clone, `../A/...` points beside the clone."""
        b = _as_repo(_template(tmp_path / "B", template_a.walk_out))

        assert f"{UNRESOLVED} '../A/extensions/context.py'" in (
            _render(b, tmp_path / "out").stderr
        )

    @pytest.mark.parametrize("as_repo", [False, True], ids=["local", "git-clone"])
    @pytest.mark.parametrize("spelling", ["driveless_posix", "driveless_native"])
    def test_driveless_absolute_spec_loads_from_anywhere(
        self, template_a: Spellings, tmp_path: Path, spelling: str, as_repo: bool
    ) -> None:
        """D17: an absolute path without a drive letter resolves from anywhere."""
        b = _template(tmp_path / "B", getattr(template_a, spelling))
        if as_repo:
            _as_repo(b)

        assert _render(b, tmp_path / "out").output == "from A"

    @pytest.mark.skipif(not ON_WINDOWS, reason="only Windows paths carry a drive colon")
    @pytest.mark.parametrize("as_repo", [False, True], ids=["local", "git-clone"])
    @pytest.mark.parametrize(
        "spelling", ["drive_absolute_posix", "drive_absolute_native"]
    )
    def test_drive_letter_spec_splits_at_the_drive_colon(
        self, template_a: Spellings, tmp_path: Path, spelling: str, as_repo: bool
    ) -> None:
        """D17: `C:/...:Class` splits at the first colon and looks for module `C`."""
        b = _template(tmp_path / "B", getattr(template_a, spelling))
        if as_repo:
            _as_repo(b)

        assert f"{UNRESOLVED} '{template_a.drive_letter}'" in (
            _render(b, tmp_path / "out").stderr
        )


# ------------------------------------------------------------------ S19

PROBE_FILTER = '''"""Probe filter for release {release}."""

from jinja2.ext import Extension


class ProbeFilter(Extension):
    def __init__(self, environment):
        super().__init__(environment)
        environment.filters["probe_shout"] = lambda v: "{release}:" + str(v).upper()
'''
DESCENDANT_HOOK = '''"""Descendant-only context hook."""

from copier_template_extensions import ContextHook


class StHook(ContextHook):
    def hook(self, context):
        context["st_marker"] = "ST-HOOK"
'''


def _file_path_extensions(ref: str, release: Path) -> None:
    """Ship a filter in project and a context hook in streamlit, both by file path."""
    project, streamlit = release / "project", release / "streamlit"
    substitute(
        project / "copier.yml",
        "  - _extensions/context.py:ContextUpdater\n",
        "  - _extensions/context.py:ContextUpdater\n  - extensions/ctx.py:ProbeFilter\n",
    )
    substitute(
        project / "copier.yml", "  - _extensions\n", "  - _extensions\n  - extensions\n"
    )
    write(project / "extensions" / "ctx.py", PROBE_FILTER.format(release=f"R{ref[1:]}"))
    write(project / "project_shout.txt.jinja", "{{ project_name | probe_shout }}\n")
    write(project / "project_marker.txt.jinja", "{{ st_marker | default('absent') }}\n")
    substitute(
        streamlit / "copier.yml",
        f"_jinja_extensions:\n  - {LOADER}\n",
        f"_jinja_extensions:\n  - {LOADER}\n  - extensions/st.py:StHook\n",
    )
    substitute(streamlit / "copier.yml", "  - .svn\n", "  - .svn\n  - extensions\n")
    write(streamlit / "extensions" / "st.py", DESCENDANT_HOOK)
    write(
        streamlit / "streamlit_shout.txt.jinja",
        "{{ project_name | probe_shout }}\n{{ st_marker }}\n",
    )


class FilePathSetup(NamedTuple):
    """The S19 releases, repositories and git-backed v1 project."""

    releases: dict[str, Path]
    repos: dict[str, Path]
    project: Path


@pytest.fixture(scope="module")
def file_path_setup(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[FilePathSetup]:
    """Compose v1; streamlit's render loads project's v1 filter file."""
    root = tmp_path_factory.mktemp("file-path")
    with temp_dir_inside(root):
        releases = build_releases(root, ("v1", "v2"), _file_path_extensions)
        repos = build_repos(root, releases)
        project = root / "composed" / "probe-app"
        compose_project("streamlit", project, ANSWERS, releases["v1"])
        make_git_project(project, repos, "v1")
        yield FilePathSetup(releases, repos, project)


@pytest.mark.xdist_group("S19-family")
class TestRegistrationOnTheFamily:
    """S19: app uses the filter docs ships, once composing registers it."""

    def test_descendant_cannot_use_the_ancestors_filter_unregistered(
        self, family: Family, tmp_path: Path
    ) -> None:
        """S19: the full view loads no ancestor file, so app has no `docs_anchor`."""
        templates = templates_at(family, tmp_path, FIRST_RELEASES)

        with pytest.raises(
            TemplateAssertionError, match="No filter named 'docs_anchor'"
        ):
            render_full_view(
                "app",
                tmp_path / "family-app",
                context_data={"project_name": FAMILY_PROJECT},
                templates_dir=templates,
            )

    def test_registered_filter_renders_in_the_descendant(
        self, family: Family, tmp_path: Path
    ) -> None:
        """S19: registered as a module, docs' filter renders in app's file."""
        project = compose_family(family, tmp_path, "app", FIRST_RELEASES)

        assert (
            "The overview lives in the [documentation](docs/index.md#family-app)."
            in lines(project / "APP.md")
        )


@pytest.mark.xdist_group("S19-compose")
class TestRegistrationAtCompose:
    """S19: composing with an ancestor's file-path hook used by a descendant."""

    def test_descendant_hook_stays_out_of_the_ancestors_files(
        self, file_path_setup: FilePathSetup
    ) -> None:
        """S19: streamlit's file-path hook never reaches project's render."""
        assert lines(file_path_setup.project / "project_marker.txt") == ["absent"]


# ------------------------------------------------------------------ S19, family

ANCESTOR_BEFORE = {"core": "1.0.0", "service": "1.0.0", "docs": "1.0.0", "app": "1.0.0"}
ANCESTOR_AFTER = {**ANCESTOR_BEFORE, "docs": "1.2.0"}
OLD_LINK = "(docs/index.md#family-app)"
NEW_LINK = "(docs/index.md#family_app)"


class AncestorMove(NamedTuple):
    """The diamond after app is updated while only docs moves.

    Attributes:
        project: The updated project.
        copies: App's `APP.md` as each render of the update left it, keyed by
            role.
    """

    project: Path
    copies: dict[str, str | None]


def _update_app_with_docs_moved(
    family: Family, work: Path, worker: type[ScopedWorker] | None = None
) -> AncestorMove:
    """Compose the diamond at docs 1.0.0, edit APP.md, update app with docs at 1.2.0."""
    project = compose_family(family, work, "app", ANCESTOR_BEFORE)
    add_user_line(project / "APP.md", prepend=True)
    recorder, recording = recording_worker(["APP.md"], worker or ScopedWorker)
    update_family_layer(
        family,
        project,
        root="app",
        layer="app",
        before=ANCESTOR_BEFORE,
        after=ANCESTOR_AFTER,
        work=work,
        worker_type=recorder,
    )
    return AncestorMove(project, {r: c["APP.md"] for r, c in recording.copies.items()})


@pytest.fixture(scope="module")
def ancestor_move(
    family: Family, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[AncestorMove]:
    """Update app to the same release while docs moves from 1.0.0 to 1.2.0."""
    work = tmp_path_factory.mktemp("ancestor-move")
    with temp_dir_inside(work):
        yield _update_app_with_docs_moved(family, work)


@pytest.mark.xdist_group("S19-ancestor-move")
class TestRegistrationPerRelease:
    """S19: each render of an update loads the ancestor's filter of its own release."""

    def test_old_copy_renders_with_the_recorded_releases_filter(
        self, ancestor_move: AncestorMove
    ) -> None:
        """S19: docs 1.0.0's filter joins the words with hyphens."""
        assert OLD_LINK in (ancestor_move.copies["old_copy"] or "")

    @pytest.mark.parametrize("role", ["in_place", "new_copy"])
    def test_renders_at_the_target_use_the_target_releases_filter(
        self, ancestor_move: AncestorMove, role: str
    ) -> None:
        """S19: docs 1.2.0's filter joins them with underscores."""
        assert NEW_LINK in (ancestor_move.copies[role] or "")

    def test_the_filter_change_lands_in_the_project(
        self, ancestor_move: AncestorMove
    ) -> None:
        """S19: the old-to-new difference applies to app's file."""
        assert any(NEW_LINK in line for line in lines(ancestor_move.project / "APP.md"))

    def test_the_users_edit_elsewhere_in_the_file_survives(
        self, ancestor_move: AncestorMove
    ) -> None:
        """S19: the line the user prepended stays first."""
        assert lines(ancestor_move.project / "APP.md")[0] == USER_LINE

    def test_the_update_merges_without_conflict(
        self, ancestor_move: AncestorMove
    ) -> None:
        """S19: nothing is left to resolve."""
        assert merge_state(ancestor_move.project) == CLEAN


@pytest.mark.xdist_group("S19-by-ref")
class TestViewKeyedByRefDefect:
    """S19: a view keyed by template ref cannot tell the old copy from the new."""

    @pytest.fixture(scope="class")
    def by_ref(
        self, family: Family, tmp_path_factory: pytest.TempPathFactory
    ) -> Iterator[AncestorMove]:
        """Run the ancestor-only update through a worker that keys views by ref."""
        work = tmp_path_factory.mktemp("by-ref")
        with temp_dir_inside(work):
            yield _update_app_with_docs_moved(
                family, work, by_ref_worker("1.0.0", "1.0.0")
            )

    def test_old_copy_renders_the_target_releases_filter(
        self, by_ref: AncestorMove
    ) -> None:
        """S19: app's ref is 1.0.0 in both, so the old copy gets the target view."""
        assert NEW_LINK in (by_ref.copies.get("old_copy") or "")

    def test_update_silently_keeps_the_old_output(self, by_ref: AncestorMove) -> None:
        """S19: old and new copies agree, so no difference reaches app's file."""
        assert any(OLD_LINK in line for line in lines(by_ref.project / "APP.md"))

    def test_update_reports_no_conflict(self, by_ref: AncestorMove) -> None:
        """S19: nothing flags that the filter change was missed."""
        assert merge_state(by_ref.project) == CLEAN
