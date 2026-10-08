"""A layer's scoped view holds its own and its ancestors' questions and extensions only.

Scenarios C1-C4 compose the made-up family's ``core`` and ``service`` layers
under the scoped and the full view and walk both layers through their next
release; ``service`` declares a context hook that defines ``container_user``,
which must stay out of ``core``'s files. S11 is the family's diamond (``docs``
extends ``core``; ``app`` extends ``service`` and ``docs``); S22 is a
three-layer chain, which the family has no shape for.

What the family cannot express stays on the bundled ``project`` and
``streamlit`` layers, in the classes marked as such. The family's hook and
filters are file-path extensions, which no view carries, so a descendant's
hook leaking under the full view needs an importable one, as does a view
carrying the extension of a layer it descends from. And the full view renders
every layer under one extension union, which cannot give app the docs filter
it needs, so the diamond's full-view claims stay on bundled-style layers too.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any, NamedTuple

import pytest

from tests.boilerplate.templates.conftest import (
    commit_all,
    compose_project,
    layer_chain,
    layer_view,
    recorded_answers,
    render_full_view,
    update_layer,
)
from tests.integration.boilerplate.composition.family import Family
from tests.integration.boilerplate.composition.scenarios.builders import (
    ANSWERS,
    AUTHOR,
    CLEAN,
    FAMILY_PROJECT,
    PROJECT_QUESTIONS,
    PROJECT_RECORDED,
    TEMPLATES,
    USER_LINE,
    add_user_line,
    answers_file,
    build_releases,
    build_repos,
    compose_family,
    copy_project,
    extensions_on_path,
    lines,
    make_git_project,
    merge_state,
    on_own_worker,
    substitute,
    temp_dir_inside,
    templates_at,
    tree,
    update_family_layer,
    write,
)
from tests.integration.boilerplate.composition.scenarios.extensions.leak_hook import (
    LEAKED,
)

LOADER = "copier_template_extensions.TemplateExtensionLoader"
SLUGIFY = "boilerplate.templates._jinja_extensions.slugify:SlugifyExtension"
LEAK_SPEC = "leak_hook:LeakHook"
SHOUT_SPEC = "shout:ShoutExtension"
ORDERS = [("project", "streamlit"), ("streamlit", "project")]
FAMILY_ORDERS = [("core", "service"), ("service", "core")]

CORE_QUESTIONS = frozenset(
    {
        "project_name",
        "package_name",
        "author_name",
        "python_version",
        "use_tests",
        "api_token",
    }
)
# What core's answers file records: hidden and secret questions are not.
CORE_RECORDED = CORE_QUESTIONS - {"package_name", "api_token"}
SERVICE_BEFORE = {"core": "1.0.0", "service": "1.0.0"}
SERVICE_AFTER = {"core": "1.1.0", "service": "1.1.0"}
DIAMOND = ("core", "service", "docs", "app")
DIAMOND_BEFORE = {"core": "1.0.0", "service": "1.0.0", "docs": "1.0.0", "app": "1.0.0"}
# Docs and app move to 1.1.0; app 1.1.0 overrides core's `license`, which only
# core 1.1.0 declares, so the views see core 1.1.0 while the project keeps 1.0.0.
DIAMOND_AFTER = {"core": "1.1.0", "service": "1.0.0", "docs": "1.1.0", "app": "1.1.0"}
FAMILY_ANSWERS = {"project_name": FAMILY_PROJECT, "author_name": AUTHOR}


def _order_id(order: tuple[str, ...]) -> str:
    return "-then-".join(order)


# ------------------------------------------------------------------ C1-C4


class ServiceViews(NamedTuple):
    """The family's core and service composed under each view, before git."""

    work: Path
    templates: Path
    composed: dict[str, Path]
    trees: dict[str, dict[str, str]]


@pytest.fixture(scope="module")
def service_views(
    family: Family, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[ServiceViews]:
    """Compose service over core at their first releases under each view."""
    work = tmp_path_factory.mktemp("views")
    with temp_dir_inside(work):
        templates = templates_at(family, work, SERVICE_BEFORE)
        composed = {
            "scoped": work / "composed" / "scoped" / "family-app",
            "full": work / "composed" / "full" / "family-app",
        }
        compose_project("service", composed["scoped"], FAMILY_ANSWERS, templates)
        render_full_view(
            "service",
            composed["full"],
            context_data=FAMILY_ANSWERS,
            templates_dir=templates,
        )
        yield ServiceViews(
            work, templates, composed, {m: tree(p) for m, p in composed.items()}
        )


@pytest.mark.xdist_group("views-service")
class TestScopedViews:
    """C1: what each layer's scoped view holds."""

    def test_core_view_holds_only_its_own_questions(
        self, service_views: ServiceViews
    ) -> None:
        """C1: core's scoped view asks no question a descendant declares."""
        view = layer_view("core", service_views.templates)

        assert set(view.questions) == CORE_QUESTIONS

    def test_service_view_adds_its_own_question(
        self, service_views: ServiceViews
    ) -> None:
        """C1: service's scoped view is core's plus service's own `port`."""
        view = layer_view("service", service_views.templates)

        assert set(view.questions) == CORE_QUESTIONS | {"port"}


@pytest.mark.xdist_group("views-service")
class TestComposeUnderEachView:
    """C2-C3: what a compose under each view writes."""

    def test_views_write_the_same_files_and_differ_only_in_core_s_answers(
        self, service_views: ServiceViews
    ) -> None:
        """C2: service's hook leaves core's files alone under either view.

        The two views write one file set, and only core's answers file
        differs, because the full view records service's question there.
        """
        full, scoped = service_views.trees["full"], service_views.trees["scoped"]

        assert (
            set(full) == set(scoped),
            sorted(p for p in full if full[p] != scoped[p]),
        ) == (True, [".copier-answers.core.yml"])

    @pytest.mark.parametrize("mode", ["scoped", "full"])
    def test_service_hook_defines_the_container_user_in_its_own_files(
        self, service_views: ServiceViews, mode: str
    ) -> None:
        """C2: the hook reaches service's Dockerfile under either view."""
        assert "USER service" in service_views.trees[mode]["Dockerfile"].splitlines()

    @pytest.mark.parametrize(
        ("mode", "core_keys"),
        [
            pytest.param("scoped", CORE_RECORDED, id="scoped-records-own-view"),
            pytest.param(
                "full",
                CORE_RECORDED | {"port"},
                id="full-records-descendant-question",
            ),
        ],
    )
    def test_core_answers_file_records_the_questions_of_its_view(
        self,
        service_views: ServiceViews,
        mode: str,
        core_keys: frozenset[str],
    ) -> None:
        """C3: only the full view records service's question in core's file."""
        recorded = recorded_answers(service_views.composed[mode], "core")

        assert set(recorded) == core_keys

    @pytest.mark.parametrize("mode", ["scoped", "full"])
    def test_service_answers_file_records_its_whole_view(
        self, service_views: ServiceViews, mode: str
    ) -> None:
        """C3: service's file records core's answers and its own either way."""
        recorded = recorded_answers(service_views.composed[mode], "service")

        assert set(recorded) == CORE_RECORDED | {"port"}


class Walk(NamedTuple):
    """A project walked through its next releases, and the view it was walked under."""

    project: Path
    mode: str


@pytest.fixture(
    scope="module",
    params=[
        on_own_worker((m, o), f"{m}-{_order_id(o)}")
        for m in ("scoped", "full")
        for o in FAMILY_ORDERS
    ],
)
def walk(
    request: pytest.FixtureRequest,
    family: Family,
    service_views: ServiceViews,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[Walk]:
    """Update both layers to their next releases in one order, under one view."""
    mode, order = request.param
    root = tmp_path_factory.mktemp(f"walk-{mode}")
    with temp_dir_inside(root):
        project = copy_project(service_views.composed[mode], root / "family-app")
        make_git_project(project, family.repos, SERVICE_BEFORE)
        add_user_line(project / "README.md")
        for layer in order:
            update_family_layer(
                family,
                project,
                root="service",
                layer=layer,
                before=SERVICE_BEFORE,
                after=SERVICE_AFTER,
                work=root,
                full_view=mode == "full",
            )
            commit_all(project, f"update {layer} to {SERVICE_AFTER[layer]}")
        yield Walk(project, mode)


class TestWalkThroughReleases:
    """C4: updating both layers to their next releases, in each order and view."""

    def test_walk_merges_without_conflict(self, walk: Walk) -> None:
        """C4: two updates leave no markers, reject files or unmerged paths."""
        assert merge_state(walk.project) == CLEAN

    def test_walk_keeps_the_user_line(self, walk: Walk) -> None:
        """C4: the line the user appended to README survives every update once."""
        assert (walk.project / "README.md").read_text(encoding="utf-8").count(
            USER_LINE
        ) == 1

    def test_walk_records_the_last_release_for_every_layer(self, walk: Walk) -> None:
        """C4: both answers files end at their layer's next release."""
        commits = {
            layer: answers_file(walk.project, layer)["_commit"]
            for layer in ("core", "service")
        }

        assert commits == SERVICE_AFTER

    def test_walk_renders_every_layer_change_at_the_last_release(
        self, walk: Walk
    ) -> None:
        """C4: core's new LICENSE appears and service's port takes its new type."""
        state = {
            "LICENSE": lines(walk.project / "LICENSE")[0],
            "port": recorded_answers(walk.project, "service")["port"],
        }

        assert state == {"LICENSE": "MIT License", "port": 8000}


# The family's hook and filters are file-path extensions, which no view carries.
# The bundled layers' importable ones show what the views do with a descendant's
# extension: streamlit declares a hook that overwrites `description`, so a file
# rendering LEAKED shows a descendant's extension reached it.


def _leaking_releases(ref: str, release: Path) -> None:
    """Give streamlit the leak hook; v2 adds a project file that renders it."""
    streamlit = release / "streamlit"
    substitute(
        streamlit / "copier.yml",
        f"_jinja_extensions:\n  - {LOADER}\n",
        f"_jinja_extensions:\n  - {LOADER}\n  - {LEAK_SPEC}\n",
    )
    if ref == "v2":
        write(
            release / "project" / "project_own.txt.jinja",
            "description={{ description }}\nrelease=v2\n",
        )


class LeakSetup(NamedTuple):
    """The releases, repositories and v1 composes the leak scenarios share."""

    releases: dict[str, Path]
    repos: dict[str, Path]
    composed: dict[str, Path]
    trees: dict[str, dict[str, str]]


@pytest.fixture(scope="module")
def leak(tmp_path_factory: pytest.TempPathFactory) -> Iterator[LeakSetup]:
    """Compose v1 under each view; keep the trees as composed, before git."""
    root = tmp_path_factory.mktemp("leak")
    with temp_dir_inside(root), extensions_on_path():
        releases = build_releases(root, ("v1", "v2"), _leaking_releases)
        repos = build_repos(root, releases)
        composed = {
            "scoped": root / "composed" / "scoped" / "probe-app",
            "full": root / "composed" / "full" / "probe-app",
        }
        compose_project("streamlit", composed["scoped"], ANSWERS, releases["v1"])
        render_full_view(
            "streamlit",
            composed["full"],
            context_data=ANSWERS,
            templates_dir=releases["v1"],
        )
        yield LeakSetup(
            releases, repos, composed, {m: tree(p) for m, p in composed.items()}
        )


@pytest.mark.xdist_group("views-leak")
class TestImportableExtensionsInViews:
    """C1-C2, C4 on the bundled layers: a descendant's importable extension."""

    def test_project_view_carries_no_descendant_extension(
        self, leak: LeakSetup
    ) -> None:
        """C1: project's scoped view loads only its own importable extensions."""
        view = layer_view("project", leak.releases["v1"])

        assert view.extensions == (SLUGIFY, LOADER)

    def test_streamlit_view_adds_its_own_extension(self, leak: LeakSetup) -> None:
        """C1: streamlit's scoped view is project's plus streamlit's own."""
        view = layer_view("streamlit", leak.releases["v1"])

        assert view.extensions == (SLUGIFY, LOADER, LEAK_SPEC)

    @pytest.mark.parametrize(
        ("mode", "leaked"),
        [
            pytest.param(
                "full",
                ["README.md", "pyproject.toml", "src/probe_app/__init__.py"],
                id="full-view-leaks-into-project-files",
            ),
            pytest.param(
                "scoped", ["README.md"], id="scoped-view-keeps-it-to-streamlit"
            ),
        ],
    )
    def test_descendant_hook_reaches_only_the_files_its_view_renders(
        self, leak: LeakSetup, mode: str, leaked: list[str]
    ) -> None:
        """C2: under the full view a descendant's hook rewrites ancestor files.

        Under the scoped view only streamlit's own README (which overwrites
        project's) renders the hook's value.
        """
        found = sorted(p for p, text in leak.trees[mode].items() if LEAKED in text)

        assert found == leaked

    def test_views_write_the_same_files_and_differ_only_where_the_hook_reaches(
        self, leak: LeakSetup
    ) -> None:
        """C2: the two views write one file set; three files differ in content."""
        full, scoped = leak.trees["full"], leak.trees["scoped"]

        assert (
            set(full) == set(scoped),
            sorted(p for p in full if full[p] != scoped[p]),
        ) == (
            True,
            [
                ".copier-answers.project.yml",
                "pyproject.toml",
                "src/probe_app/__init__.py",
            ],
        )

    @pytest.mark.parametrize("mode", ["scoped", "full"])
    def test_project_file_renders_the_description_its_view_allows(
        self, leak: LeakSetup, mode: str, tmp_path: Path
    ) -> None:
        """C4: updates under the full view keep rendering the descendant's hook.

        Under the scoped view the project-owned file added by the update
        renders the answer.
        """
        with extensions_on_path():
            project = copy_project(leak.composed[mode], tmp_path / "probe-app")
            make_git_project(project, leak.repos, "v1")
            update_layer(
                project,
                root="streamlit",
                layer="project",
                source=leak.repos["project"],
                ref="v2",
                templates=leak.releases,
                full_view=mode == "full",
            )
        expected = LEAKED if mode == "full" else ANSWERS["description"]

        assert f"description={expected}" in lines(project / "project_own.txt")


# ------------------------------------------------------------------ S11


class Diamond(NamedTuple):
    """The family's diamond composed at its first releases, git-backed."""

    work: Path
    project: Path


@pytest.fixture(scope="module")
def diamond(
    family: Family, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[Diamond]:
    """Compose the diamond: core, service, docs and app."""
    work = tmp_path_factory.mktemp("diamond")
    with temp_dir_inside(work):
        project = compose_family(
            family, work, "app", DIAMOND_BEFORE, {"author_name": AUTHOR}
        )
        yield Diamond(work, project)


@pytest.mark.xdist_group("views-diamond")
class TestDiamond:
    """S11: views, answers and renders of the family's diamond at its first releases."""

    def test_app_composes_its_ancestors_in_topological_order(
        self, family: Family, diamond: Diamond
    ) -> None:
        """S11: the resolver orders the diamond core, service, docs, app."""
        templates = templates_at(family, diamond.work, DIAMOND_BEFORE)

        assert layer_chain("app", templates) == list(DIAMOND)

    def test_each_scoped_view_holds_its_own_and_transitive_ancestors_questions(
        self, family: Family, diamond: Diamond
    ) -> None:
        """S11: each layer's view adds exactly the questions of its own ancestry."""
        templates = templates_at(family, diamond.work, DIAMOND_BEFORE)
        added = {
            layer: set(layer_view(layer, templates).questions) - CORE_QUESTIONS
            for layer in DIAMOND
        }
        docs = {"docs_generator", "docs_site_name"}

        assert added == {
            "core": set(),
            "service": {"port"},
            "docs": docs,
            "app": {"port"} | docs,
        }

    def test_each_answers_file_records_the_questions_of_its_scoped_view(
        self, diamond: Diamond
    ) -> None:
        """S11: answers files beyond the shared keys follow each layer's view."""
        recorded = {
            layer: set(recorded_answers(diamond.project, layer)) - CORE_RECORDED
            for layer in DIAMOND
        }
        docs = {"docs_generator", "docs_site_name"}

        assert recorded == {
            "core": set(),
            "service": {"port"},
            "docs": docs,
            "app": {"port"} | docs,
        }

    def test_docs_and_app_files_render_through_the_ancestors_filter(
        self, diamond: Diamond
    ) -> None:
        """S11: docs' index and app's guide render, app through docs' anchor filter."""
        rendered = {
            "docs/index.md": lines(diamond.project / "docs" / "index.md")[2],
            "APP.md": lines(diamond.project / "APP.md")[4],
        }

        assert rendered == {
            "docs/index.md": "Welcome to Family App documentation, built with mkdocs.",
            "APP.md": "The overview lives in the [documentation](docs/index.md#family-app).",
        }


DIAMOND_FILES = ("docs/index.md", "APP.md")


@pytest.fixture(scope="module")
def diamond_walk(family: Family, diamond: Diamond) -> Iterator[Path]:
    """Prepend a user line to both files, then update docs and app."""
    with temp_dir_inside(diamond.work):
        project = copy_project(diamond.project, diamond.work / "walk" / "family-app")
        for name in DIAMOND_FILES:
            add_user_line(project / name, prepend=True)
        for layer in ("docs", "app"):
            update_family_layer(
                family,
                project,
                root="app",
                layer=layer,
                before=DIAMOND_BEFORE,
                after=DIAMOND_AFTER,
                work=diamond.work,
            )
            commit_all(project, f"update {layer} to {DIAMOND_AFTER[layer]}")
        yield project


class TestDiamondUpdates:
    """S11: updating docs then app to their next releases."""

    def test_updates_merge_without_conflict(self, diamond_walk: Path) -> None:
        """S11: updating docs then app leaves nothing to resolve."""
        assert merge_state(diamond_walk) == CLEAN

    def test_updates_keep_the_user_line_at_the_top(self, diamond_walk: Path) -> None:
        """S11: the prepended user line stays first in both files."""
        firsts = [lines(diamond_walk / name)[0] for name in DIAMOND_FILES]

        assert firsts == [USER_LINE, USER_LINE]

    def test_only_the_updated_layers_move(self, diamond_walk: Path) -> None:
        """S11: docs and app record their next release; core and service stay."""
        commits = {
            layer: answers_file(diamond_walk, layer)["_commit"] for layer in DIAMOND
        }

        assert commits == {
            "core": "1.0.0",
            "service": "1.0.0",
            "docs": "1.1.0",
            "app": "1.1.0",
        }


# ------------------------------------------------------------------ S11, bundled
#
# The diamond on bundled-style layers: ``docs`` extends ``project`` and ships an
# importable filter; ``app`` extends ``streamlit`` and ``docs``. The full view
# renders every layer under one extension union, so it can give app the filter
# the family's file-path one cannot reach, and a release can change a line in
# docs' and app's files for an edit to conflict with.

ANSWERS_STUB = "{{_copier_conf.answers_file}}.jinja"
EXCLUDE = (
    '_exclude:\n  - "/copier.yaml"\n  - "/copier.yml"\n  - "/boilerplate.yml"\n'
    '  - "~*"\n  - "*.py[co]"\n  - __pycache__\n  - .git\n'
)
BUNDLED_DIAMOND = ("project", "streamlit", "docs", "app")
BUNDLED_FILES = ("docs/index.md", "app.txt")


def _metadata(name: str, version: str, extends: list[str]) -> str:
    parents = "".join(f"  - {e}\n" for e in extends)
    return (
        f'schema_version: "1"\nname: {name}\nversion: {version}\n'
        f"description: Probe {name} layer\nextends:\n{parents}"
    )


def _diamond_layers(ref: str, release: Path) -> None:
    """Add docs (own question, shout filter) and app (no question) at `ref`."""
    stub = (TEMPLATES / "project" / ANSWERS_STUB).read_text(encoding="utf-8")
    version = "0.1.0" if ref == "v1" else "0.2.0"
    docs, app = release / "docs", release / "app"
    write(docs / "boilerplate.yml", _metadata("docs", version, ["project"]))
    write(
        docs / "copier.yml",
        "_answers_file: .copier-answers.docs.yml\n"
        + EXCLUDE
        + f"_jinja_extensions:\n  - {SHOUT_SPEC}\n"
        + 'docs_site:\n  type: str\n  help: "Docs site hostname."\n'
        + '  default: "{{ project_slug }}.docs.example"\n',
    )
    write(docs / ANSWERS_STUB, stub)
    write(
        docs / "docs" / "index.md.jinja",
        "# {{ project_name }} docs\nsite={{ docs_site | shout }}\n"
        + ("author={{ author_name }}\n" if ref == "v2" else "")
        + f"release={ref}\n",
    )
    write(app / "boilerplate.yml", _metadata("app", version, ["streamlit", "docs"]))
    write(app / "copier.yml", "_answers_file: .copier-answers.app.yml\n" + EXCLUDE)
    write(app / ANSWERS_STUB, stub)
    write(
        app / "app.txt.jinja",
        "project_name={{ project_name }}\ndocs_site={{ docs_site | shout }}\n"
        f"container_registry={{{{ container_registry }}}}\nrelease={ref}\n",
    )


class BundledDiamond(NamedTuple):
    """The releases, repositories and v1 composes the bundled diamond shares."""

    releases: dict[str, Path]
    repos: dict[str, Path]
    composed: dict[str, Path]


@pytest.fixture(scope="module")
def bundled_diamond(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[BundledDiamond]:
    """Compose the diamond at v1 under each view; only docs and app get v2."""
    root = tmp_path_factory.mktemp("bundled-diamond")
    with temp_dir_inside(root), extensions_on_path():
        releases = build_releases(
            root, ("v1", "v2"), _diamond_layers, merge_readme=False
        )
        repos = build_repos(root, releases, {"project": ["v1"], "streamlit": ["v1"]})
        composed = {
            "scoped": root / "composed" / "scoped" / "probe-app",
            "full": root / "composed" / "full" / "probe-app",
        }
        compose_project("app", composed["scoped"], ANSWERS, releases["v1"])
        render_full_view(
            "app", composed["full"], context_data=ANSWERS, templates_dir=releases["v1"]
        )
        yield BundledDiamond(releases, repos, composed)


@pytest.mark.xdist_group("views-bundled-diamond")
class TestBundledDiamond:
    """S11 on the bundled layers: the extension and the full view."""

    def test_docs_extension_reaches_only_views_that_descend_from_docs(
        self, bundled_diamond: BundledDiamond
    ) -> None:
        """S11: the shout filter is in docs' and app's views, not the others'."""
        carries = {
            layer: SHOUT_SPEC
            in layer_view(layer, bundled_diamond.releases["v1"]).extensions
            for layer in BUNDLED_DIAMOND
        }

        assert carries == {
            "project": False,
            "streamlit": False,
            "docs": True,
            "app": True,
        }

    def test_full_view_records_everything_everywhere(
        self, bundled_diamond: BundledDiamond
    ) -> None:
        """S11: under the full view every answers file records every question."""
        recorded = {
            layer: set(recorded_answers(bundled_diamond.composed["full"], layer))
            - PROJECT_RECORDED
            for layer in BUNDLED_DIAMOND
        }

        assert recorded == {
            layer: {"container_registry", "docs_site"} for layer in BUNDLED_DIAMOND
        }

    def test_full_view_files_render_through_the_ancestors_filter(
        self, bundled_diamond: BundledDiamond
    ) -> None:
        """S11: docs' and app's files render docs_site through docs' filter."""
        rendered = {
            name: lines(bundled_diamond.composed["full"] / name)
            for name in BUNDLED_FILES
        }

        assert rendered == {
            "docs/index.md": [
                "# Probe App docs",
                "site=PROBE-APP.DOCS.EXAMPLE!",
                "release=v1",
            ],
            "app.txt": [
                "project_name=Probe App",
                "docs_site=PROBE-APP.DOCS.EXAMPLE!",
                "container_registry=ghcr.io",
                "release=v1",
            ],
        }


def _update_bundled_diamond(project: Path, diamond: BundledDiamond, mode: str) -> None:
    for layer in ("docs", "app"):
        update_layer(
            project,
            root="app",
            layer=layer,
            source=diamond.repos[layer],
            ref="v2",
            templates=diamond.releases,
            full_view=mode == "full",
        )
        commit_all(project, f"update {layer} to v2")


@pytest.fixture(
    scope="module",
    params=[on_own_worker("full", "diamond-full")],
)
def bundled_diamond_walk(
    request: pytest.FixtureRequest,
    bundled_diamond: BundledDiamond,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[Path]:
    """Prepend a user line to both files, then update docs and app to v2."""
    mode: str = request.param
    root = tmp_path_factory.mktemp(f"bundled-diamond-{mode}")
    with temp_dir_inside(root), extensions_on_path():
        project = copy_project(bundled_diamond.composed[mode], root / "probe-app")
        make_git_project(project, bundled_diamond.repos, "v1")
        for name in BUNDLED_FILES:
            add_user_line(project / name, prepend=True)
        _update_bundled_diamond(project, bundled_diamond, mode)
        yield project


class TestBundledDiamondUpdates:
    """S11 on the bundled layers: updating docs then app to v2 under the full view."""

    def test_updates_merge_without_conflict(self, bundled_diamond_walk: Path) -> None:
        """S11: updating docs then app leaves nothing to resolve."""
        assert merge_state(bundled_diamond_walk) == CLEAN

    def test_updates_keep_the_user_line_at_the_top(
        self, bundled_diamond_walk: Path
    ) -> None:
        """S11: the prepended user line stays first in both files."""
        firsts = [lines(bundled_diamond_walk / name)[0] for name in BUNDLED_FILES]

        assert firsts == [USER_LINE, USER_LINE]

    def test_docs_file_gains_the_ancestor_answer_v2_renders(
        self, bundled_diamond_walk: Path
    ) -> None:
        """S11: docs v2 renders author_name, an answer project's file records."""
        assert lines(bundled_diamond_walk / "docs/index.md")[-2:] == [
            "author=Ada Probe",
            "release=v2",
        ]

    def test_only_the_updated_layers_move_to_v2(
        self, bundled_diamond_walk: Path
    ) -> None:
        """S11: docs and app record v2; project and streamlit stay at v1."""
        commits = {
            layer: answers_file(bundled_diamond_walk, layer)["_commit"]
            for layer in BUNDLED_DIAMOND
        }

        assert commits == {
            "project": "v1",
            "streamlit": "v1",
            "docs": "v2",
            "app": "v2",
        }

    @pytest.mark.xdist_group("views-bundled-diamond-adjacent")
    @pytest.mark.parametrize("mode", ["scoped", "full"])
    def test_edit_beside_a_changed_line_conflicts_in_either_view(
        self, bundled_diamond: BundledDiamond, mode: str, tmp_path: Path
    ) -> None:
        """S11 run 1: a user line appended right after the line v2 rewrites conflicts.

        The conflict comes from the edit's adjacency, not the view: both views
        leave the same markers.
        """
        with extensions_on_path():
            project = copy_project(
                bundled_diamond.composed[mode], tmp_path / "probe-app"
            )
            make_git_project(project, bundled_diamond.repos, "v1")
            for name in BUNDLED_FILES:
                add_user_line(project / name)
            _update_bundled_diamond(project, bundled_diamond, mode)

        assert merge_state(project).marked == sorted(BUNDLED_FILES)


# ------------------------------------------------------------------ S22
#
# The family has no three-layer chain: every layer extends core alone except app,
# which extends two, so the chain stays on the bundled layers.

CHAIN = ("project", "streamlit", "extra")
CHAIN_FILES = ("project_own.txt", "inherited.txt", "extra.txt")
EXTRA_METADATA = _metadata("extra", "0.1.0", ["streamlit"])
EXTRA_COPIER = (
    "_answers_file: .copier-answers.extra.yml\n\n"
    'extra_flag:\n  type: str\n  help: "Extra flag"\n  default: "on"\n\n'
    'container_registry:\n  default: "registry.example.com"\n'
)


def _chain_layers(ref: str, release: Path) -> None:
    """Add extra (own question, an override of streamlit's); change a file per layer."""
    project, streamlit, extra = (release / n for n in CHAIN)
    write(extra / "boilerplate.yml", EXTRA_METADATA)
    write(extra / "copier.yml", EXTRA_COPIER)
    write(
        extra / ANSWERS_STUB,
        (TEMPLATES / "streamlit" / ANSWERS_STUB).read_text(encoding="utf-8"),
    )
    write(
        project / "project_own.txt.jinja",
        f"project_name={{{{ project_name }}}}\nrelease={ref}\n",
    )
    write(
        streamlit / "inherited.txt.jinja",
        f"author_name={{{{ author_name }}}}\nrelease={ref}\n",
    )
    write(
        extra / "extra.txt.jinja",
        "project_name={{ project_name }}\nauthor_name={{ author_name }}\n"
        "container_registry={{ container_registry }}\nextra_flag={{ extra_flag }}\n"
        f"release={ref}\n",
    )
    if ref == "v2":
        substitute(
            streamlit / "README.md.jinja",
            "# {{ project_name }}\n",
            "# {{ project_name }} (release v2)\n",
        )


class ChainSetup(NamedTuple):
    """The releases, repositories and v1 compose the S22 chain shares."""

    releases: dict[str, Path]
    repos: dict[str, Path]
    composed: Path


@pytest.fixture(scope="module")
def chain(tmp_path_factory: pytest.TempPathFactory) -> Iterator[ChainSetup]:
    """Compose the chain at v1, letting extra's registry default apply."""
    root = tmp_path_factory.mktemp("chain")
    with temp_dir_inside(root):
        releases = build_releases(root, ("v1", "v2"), _chain_layers)
        repos = build_repos(root, releases)
        composed = root / "composed" / "probe-app"
        answers = {k: v for k, v in ANSWERS.items() if k != "container_registry"}
        compose_project("extra", composed, answers, releases["v1"])
        yield ChainSetup(releases, repos, composed)


@pytest.mark.xdist_group("views-chain")
class TestChain:
    """S22: views and answers of the three-layer chain at v1."""

    def test_each_view_adds_one_layers_question(self, chain: ChainSetup) -> None:
        """S22: views grow by one question per layer down the chain."""
        added = {
            layer: set(layer_view(layer, chain.releases["v1"]).questions)
            - PROJECT_QUESTIONS
            for layer in CHAIN
        }

        assert added == {
            "project": set(),
            "streamlit": {"container_registry"},
            "extra": {"container_registry", "extra_flag"},
        }

    def test_descendant_override_reaches_every_layer_that_asks_the_question(
        self, chain: ChainSetup
    ) -> None:
        """S22: the unified pass takes extra's registry default for both askers."""
        registries = {
            layer: recorded_answers(chain.composed, layer).get("container_registry")
            for layer in CHAIN
        }

        assert registries == {
            "project": None,
            "streamlit": "registry.example.com",
            "extra": "registry.example.com",
        }

    def test_leaf_records_its_own_question(self, chain: ChainSetup) -> None:
        """S22: extra records extra_flag from its own default."""
        assert recorded_answers(chain.composed, "extra")["extra_flag"] == "on"


@pytest.fixture(
    scope="module",
    params=[on_own_worker(o, f"chain-{_order_id(o)}") for o in (CHAIN, CHAIN[::-1])],
)
def chain_walk(
    request: pytest.FixtureRequest,
    chain: ChainSetup,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[Path]:
    """Append a user line to README, then update all three layers to v2."""
    order: tuple[str, ...] = request.param
    root = tmp_path_factory.mktemp("chain-walk")
    with temp_dir_inside(root):
        project = copy_project(chain.composed, root / "probe-app")
        make_git_project(project, chain.repos, "v1")
        add_user_line(project / "README.md")
        for layer in order:
            update_layer(
                project,
                root="extra",
                layer=layer,
                source=chain.repos[layer],
                ref="v2",
                templates=chain.releases,
            )
            commit_all(project, f"update {layer} to v2")
        yield project


class TestChainUpdates:
    """S22: updating all three layers to v2, in lock and reverse order."""

    def test_updates_merge_without_conflict(self, chain_walk: Path) -> None:
        """S22: three updates in either order leave nothing to resolve."""
        assert merge_state(chain_walk) == CLEAN

    def test_updates_render_every_file_at_v2(self, chain_walk: Path) -> None:
        """S22: every layer's file and streamlit's README title reach v2."""
        state: dict[str, Any] = {
            name: lines(chain_walk / name)[-1] for name in CHAIN_FILES
        }
        state["README.md"] = lines(chain_walk / "README.md")[0]

        assert state == {
            "project_own.txt": "release=v2",
            "inherited.txt": "release=v2",
            "extra.txt": "release=v2",
            "README.md": "# Probe App (release v2)",
        }

    def test_updates_keep_the_user_line_once(self, chain_walk: Path) -> None:
        """S22: the README user line survives all three updates exactly once."""
        assert (chain_walk / "README.md").read_text(encoding="utf-8").count(
            USER_LINE
        ) == 1

    def test_every_layer_records_v2(self, chain_walk: Path) -> None:
        """S22: all three answers files end at v2."""
        commits = {layer: answers_file(chain_walk, layer)["_commit"] for layer in CHAIN}

        assert commits == dict.fromkeys(CHAIN, "v2")
