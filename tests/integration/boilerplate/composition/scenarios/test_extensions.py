"""How a layer's render can load a file-path Jinja extension another layer ships.

``copier_template_extensions`` resolves a file-path spec (``path.py:Class``)
against the rendering template's own root, so a descendant cannot name an
ancestor's file directly. D17 probes which spellings of another template's
file resolve, from a local directory and from Copier's git clone. S19
registers the ancestor's file as an importable module per ref, so a
descendant renders with the ancestor's extension at the release each copy of
an update renders. Whether a descendant can use the filter at all runs on the
made-up template family; the per-ref update variants stay on the bundled
layers, because the family's docs filter is the same file in every release, so
no registration variant renders anything different.
"""

import importlib.util
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path, PurePath
from typing import NamedTuple

import pytest
import yaml
from jinja2.exceptions import TemplateAssertionError

from boilerplate.composition.views import LayerView
from boilerplate.integrations.copier_types import Template
from tests.boilerplate.templates.conftest import (
    ScopedWorker,
    commit_all,
    compose_project,
    init_repo,
    layer_chain,
    layer_view,
    update_layer,
)
from tests.integration.boilerplate.composition.family import Family
from tests.integration.boilerplate.composition.scenarios.builders import (
    ANSWERS,
    CLEAN,
    FAMILY_PROJECT,
    build_releases,
    build_repos,
    compose_family,
    copy_project,
    lines,
    make_git_project,
    merge_state,
    on_own_worker,
    substitute,
    temp_dir_inside,
    templates_at,
    write,
)

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
SHOUT_FILES = ("streamlit_shout.txt", "project_shout.txt", "project_marker.txt")
MODULE_ROOT = "boilerplate_layer_ext"


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


def _register(patch: pytest.MonkeyPatch, path: Path, name: str) -> None:
    """Import the file at `path` as module `name`, undone when `patch` is."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    patch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)


def _ancestor_specs(copier_yml: Path) -> list[tuple[str, str]]:
    """Return ``(relative file, class)`` of each `extensions/` spec a layer declares."""
    config = yaml.safe_load(copier_yml.read_text(encoding="utf-8"))
    return [
        (spec.split(":", 1)[0], spec.split(":", 1)[1])
        for spec in config.get("_jinja_extensions", [])
        if str(spec).startswith("extensions/")
    ]


class FilePathSetup(NamedTuple):
    """The S19 releases, repositories and git-backed v1 project."""

    releases: dict[str, Path]
    repos: dict[str, Path]
    project: Path


@pytest.fixture(scope="module")
def file_path_setup(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[FilePathSetup]:
    """Compose v1, registering project's v1 filter as a module streamlit loads."""
    root = tmp_path_factory.mktemp("file-path")
    with temp_dir_inside(root), pytest.MonkeyPatch.context() as patch:
        releases = build_releases(root, ("v1", "v2"), _file_path_extensions)
        repos = build_repos(root, releases)
        module = f"{MODULE_ROOT}.project.ctx"
        _register(patch, releases["v1"] / "project" / "extensions" / "ctx.py", module)
        project = root / "composed" / "probe-app"
        compose_project(
            "streamlit",
            project,
            ANSWERS,
            releases["v1"],
            extra_extensions={"streamlit": [f"{module}:ProbeFilter"]},
        )
        make_git_project(project, repos, "v1")
        yield FilePathSetup(releases, repos, project)


def _registering_worker(
    setup: FilePathSetup, patch: pytest.MonkeyPatch, *, per_ref_names: bool
) -> type[ScopedWorker]:
    """Return a worker that registers its ancestors' extension files at each build.

    Each build clones every ancestor at the ref the worker renders, registers
    its `extensions/` files as modules and adds them to the view: under one
    module name per ref, or one name re-registered at every build.
    """

    class RegisteringWorker(ScopedWorker):
        """Add the ancestors' extensions, registered from clones at the render's ref."""

        def view_for(self, ref: str | None) -> LayerView:
            """Register the ancestors' extensions at `ref` and add them to the view."""
            view = super().view_for(ref)
            assert ref is not None
            layer = Path(str(self.src_path)).name
            specs: list[str] = []
            for ancestor in layer_chain(layer, setup.releases[ref])[:-1]:
                clone = Template(url=str(setup.repos[ancestor]), ref=ref)
                self._cleanup_hooks.append(clone._cleanup)  # pyright: ignore[reportPrivateUsage]
                for relative, cls in _ancestor_specs(
                    clone.local_abspath / "copier.yml"
                ):
                    stem = Path(relative).stem
                    name = (
                        f"{MODULE_ROOT}.{ancestor}.{ref}.{stem}"
                        if per_ref_names
                        else f"{MODULE_ROOT}.{ancestor}.{stem}"
                    )
                    _register(patch, clone.local_abspath / relative, name)
                    specs.append(f"{name}:{cls}")
            return LayerView(view.questions, (*view.extensions, *specs))

    return RegisteringWorker


VARIANTS = {
    "A-clone-per-ref-name": "R2:PROBE APP",
    "C-clone-one-name": "R2:PROBE APP",
    "B-composed-source-target-only": "R1:PROBE APP",
}


@pytest.fixture(scope="module", params=[on_own_worker(v, f"S19-{v}") for v in VARIANTS])
def registered_update(
    request: pytest.FixtureRequest,
    file_path_setup: FilePathSetup,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[tuple[str, Path]]:
    """Update streamlit then project to v2 under one registration variant."""
    variant: str = request.param
    root = tmp_path_factory.mktemp(variant)
    with temp_dir_inside(root), pytest.MonkeyPatch.context() as patch:
        project = copy_project(file_path_setup.project, root / "probe-app")
        releases = file_path_setup.releases
        for layer in ("streamlit", "project"):
            worker_type: type[ScopedWorker] = ScopedWorker
            views: dict[str, LayerView] | None = None
            if variant.startswith("B") and layer == "streamlit":
                module = f"{MODULE_ROOT}.project.ctx"
                _register(
                    patch, releases["v2"] / "project" / "extensions" / "ctx.py", module
                )
                views = {}
                for ref, release in releases.items():
                    view = layer_view(layer, release)
                    views[ref] = LayerView(
                        view.questions, (*view.extensions, f"{module}:ProbeFilter")
                    )
            elif not variant.startswith("B"):
                worker_type = _registering_worker(
                    file_path_setup, patch, per_ref_names=variant.startswith("A")
                )
            update_layer(
                project,
                root="streamlit",
                layer=layer,
                source=file_path_setup.repos[layer],
                ref="v2",
                templates=releases,
                views_by_ref=views,
                worker_type=worker_type,
            )
            commit_all(project, f"update {layer} to v2")
        yield variant, project


@pytest.mark.xdist_group("S19-family")
class TestRegistrationOnTheFamily:
    """S19: app uses the filter docs ships, once composing registers it."""

    def test_descendant_cannot_use_the_ancestors_filter_unregistered(
        self, family: Family, tmp_path: Path
    ) -> None:
        """S19: without registration app's render has no `docs_anchor` filter."""
        templates = templates_at(family, tmp_path, FIRST_RELEASES)

        with pytest.raises(
            TemplateAssertionError, match="No filter named 'docs_anchor'"
        ):
            compose_project(
                "app",
                tmp_path / "family-app",
                {"project_name": FAMILY_PROJECT},
                templates,
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


class TestRegistrationPerRef:
    """S19: updating with the ancestor's filter registered per variant."""

    def test_descendant_file_reaches_the_release_its_registration_allows(
        self, registered_update: tuple[str, Path]
    ) -> None:
        """S19: registering only the target release leaves the file at R1 silently.

        Registering from a clone at each render's ref (A, C) gives the old
        copy R1 and the new copy R2, so the update applies R1 to R2. B gives
        both copies the v2 module, so old equals new and nothing changes.
        """
        variant, project = registered_update

        assert lines(project / "streamlit_shout.txt")[0] == VARIANTS[variant]

    def test_ancestor_file_updates_through_its_own_loader(
        self, registered_update: tuple[str, Path]
    ) -> None:
        """S19: project's own file-path spec loads its filter at each ref."""
        assert lines(registered_update[1] / "project_shout.txt") == ["R2:PROBE APP"]

    def test_descendant_hook_stays_out_of_the_ancestors_files(
        self, registered_update: tuple[str, Path]
    ) -> None:
        """S19: after both updates project's marker still renders the default."""
        assert lines(registered_update[1] / "project_marker.txt") == ["absent"]

    def test_update_merges_without_conflict(
        self, registered_update: tuple[str, Path]
    ) -> None:
        """S19: no variant leaves anything to resolve."""
        assert merge_state(registered_update[1]) == CLEAN
