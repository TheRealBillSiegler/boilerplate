"""A layer's scoped view holds its own and its ancestors' questions and extensions only.

Scenarios C1-C4 compose the bundled ``project`` and ``streamlit`` layers under
the scoped and the full view and walk both layers through two more releases;
``streamlit`` declares a context hook that overwrites ``description``, so a
file rendering ``LEAKED`` shows a descendant's extension reached it. S11 is a
diamond (``docs`` extends ``project``; ``app`` extends ``streamlit`` and
``docs``); S22 is a three-layer chain (``extra`` extends ``streamlit``).
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
from tests.integration.boilerplate.composition.scenarios.builders import (
    ANSWERS,
    CLEAN,
    PROJECT_QUESTIONS,
    PROJECT_RECORDED,
    TEMPLATES,
    USER_LINE,
    add_user_line,
    answers_file,
    build_releases,
    build_repos,
    copy_project,
    extensions_on_path,
    lines,
    make_git_project,
    merge_state,
    on_own_worker,
    substitute,
    temp_dir_inside,
    tree,
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


def _order_id(order: tuple[str, ...]) -> str:
    return "-then-".join(order)


# ------------------------------------------------------------------ C1-C4


def _leaking_releases(ref: str, release: Path) -> None:
    """Give streamlit the leak hook; from v2 on, change one file per layer."""
    project, streamlit = release / "project", release / "streamlit"
    substitute(
        streamlit / "copier.yml",
        f"_jinja_extensions:\n  - {LOADER}\n",
        f"_jinja_extensions:\n  - {LOADER}\n  - {LEAK_SPEC}\n",
    )
    if ref == "v1":
        return
    substitute(
        streamlit / "README.md.jinja",
        "# {{ project_name }}\n",
        f"# {{{{ project_name }}}} (release {ref})\n",
    )
    write(
        streamlit / "inherited.txt.jinja",
        "project_name={{ project_name }}\npackage_name={{ package_name }}\n"
        f"author_name={{{{ author_name }}}}\nrelease={ref}\n",
    )
    write(
        project / "project_own.txt.jinja",
        "project_name={{ project_name }}\ndescription={{ description }}\n"
        "author_name={{ author_name }}\nsample_module={{ sample_module }}\n"
        f"release={ref}\n",
    )


class LeakSetup(NamedTuple):
    """The releases, repositories and v1 composes the C1-C4 scenarios share."""

    releases: dict[str, Path]
    repos: dict[str, Path]
    composed: dict[str, Path]
    trees: dict[str, dict[str, str]]


@pytest.fixture(scope="module")
def leak(tmp_path_factory: pytest.TempPathFactory) -> Iterator[LeakSetup]:
    """Compose v1 under each view; keep the trees as composed, before git."""
    root = tmp_path_factory.mktemp("views")
    with temp_dir_inside(root), extensions_on_path():
        releases = build_releases(root, ("v1", "v2", "v3"), _leaking_releases)
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
class TestScopedViews:
    """C1: what each layer's scoped view holds."""

    def test_project_view_holds_only_its_own_questions(self, leak: LeakSetup) -> None:
        """C1: project's scoped view asks no question a descendant declares."""
        view = layer_view("project", leak.releases["v1"])

        assert set(view.questions) == PROJECT_QUESTIONS

    def test_project_view_carries_no_descendant_extension(
        self, leak: LeakSetup
    ) -> None:
        """C1: project's scoped view loads only its own importable extensions."""
        view = layer_view("project", leak.releases["v1"])

        assert view.extensions == (SLUGIFY, LOADER)

    def test_streamlit_view_adds_its_own_question_and_extension(
        self, leak: LeakSetup
    ) -> None:
        """C1: streamlit's scoped view is project's plus streamlit's own."""
        view = layer_view("streamlit", leak.releases["v1"])

        assert (set(view.questions), view.extensions) == (
            PROJECT_QUESTIONS | {"container_registry"},
            (SLUGIFY, LOADER, LEAK_SPEC),
        )


@pytest.mark.xdist_group("views-leak")
class TestComposeUnderEachView:
    """C2-C3: what a compose under each view writes."""

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

    @pytest.mark.parametrize(
        ("mode", "project_keys"),
        [
            pytest.param("scoped", PROJECT_RECORDED, id="scoped-records-own-view"),
            pytest.param(
                "full",
                PROJECT_RECORDED | {"container_registry"},
                id="full-records-descendant-question",
            ),
        ],
    )
    def test_project_answers_file_records_the_questions_of_its_view(
        self, leak: LeakSetup, mode: str, project_keys: frozenset[str]
    ) -> None:
        """C3: only the full view records streamlit's question in project's file."""
        recorded = recorded_answers(leak.composed[mode], "project")

        assert set(recorded) == project_keys

    @pytest.mark.parametrize("mode", ["scoped", "full"])
    def test_streamlit_answers_file_records_its_whole_view(
        self, leak: LeakSetup, mode: str
    ) -> None:
        """C3: streamlit's file records project's answers and its own either way."""
        recorded = recorded_answers(leak.composed[mode], "streamlit")

        assert set(recorded) == PROJECT_RECORDED | {"container_registry"}


class Walk(NamedTuple):
    """A project walked through every release, and the view it was walked under."""

    project: Path
    mode: str


@pytest.fixture(
    scope="module",
    params=[
        on_own_worker((m, o), f"{m}-{_order_id(o)}")
        for m in ("scoped", "full")
        for o in ORDERS
    ],
)
def walk(
    request: pytest.FixtureRequest,
    leak: LeakSetup,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[Walk]:
    """Walk both layers through v2 and v3 in one order, under one view."""
    mode, order = request.param
    root = tmp_path_factory.mktemp(f"walk-{mode}")
    with temp_dir_inside(root):
        project = copy_project(leak.composed[mode], root / "probe-app")
        make_git_project(project, leak.repos, "v1")
        add_user_line(project / "README.md")
        for ref in ("v2", "v3"):
            for layer in order:
                update_layer(
                    project,
                    root="streamlit",
                    layer=layer,
                    source=leak.repos[layer],
                    ref=ref,
                    templates=leak.releases,
                    full_view=mode == "full",
                )
                commit_all(project, f"update {layer} to {ref}")
        yield Walk(project, mode)


class TestWalkThroughReleases:
    """C4: updating both layers through v2 and v3, in each order and view."""

    def test_walk_merges_without_conflict(self, walk: Walk) -> None:
        """C4: four updates leave no markers, reject files or unmerged paths."""
        assert merge_state(walk.project) == CLEAN

    def test_walk_keeps_the_user_line(self, walk: Walk) -> None:
        """C4: the line the user appended to README survives every update once."""
        assert (walk.project / "README.md").read_text(encoding="utf-8").count(
            USER_LINE
        ) == 1

    def test_walk_records_the_last_release_for_every_layer(self, walk: Walk) -> None:
        """C4: both answers files end at v3."""
        commits = {
            layer: answers_file(walk.project, layer)["_commit"]
            for layer in ("project", "streamlit")
        }

        assert commits == {"project": "v3", "streamlit": "v3"}

    def test_walk_renders_every_layer_file_at_the_last_release(
        self, walk: Walk
    ) -> None:
        """C4: each layer's changed file carries v3's content."""
        files = {
            "README.md": lines(walk.project / "README.md")[0],
            "inherited.txt": lines(walk.project / "inherited.txt")[-1],
            "project_own.txt": lines(walk.project / "project_own.txt")[-1],
        }

        assert files == {
            "README.md": "# Probe App (release v3)",
            "inherited.txt": "release=v3",
            "project_own.txt": "release=v3",
        }

    def test_project_file_renders_the_description_its_view_allows(
        self, walk: Walk
    ) -> None:
        """C4: updates under the full view keep rendering the descendant's hook.

        Under the scoped view the project-owned file renders the answer.
        """
        expected = LEAKED if walk.mode == "full" else ANSWERS["description"]

        assert f"description={expected}" in lines(walk.project / "project_own.txt")


# ------------------------------------------------------------------ S11

ANSWERS_STUB = "{{_copier_conf.answers_file}}.jinja"
EXCLUDE = (
    '_exclude:\n  - "/copier.yaml"\n  - "/copier.yml"\n  - "/boilerplate.yml"\n'
    '  - "~*"\n  - "*.py[co]"\n  - __pycache__\n  - .git\n'
)
DIAMOND = ("project", "streamlit", "docs", "app")
DIAMOND_FILES = ("docs/index.md", "app.txt")


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


class DiamondSetup(NamedTuple):
    """The releases, repositories and v1 composes the S11 diamond shares."""

    releases: dict[str, Path]
    repos: dict[str, Path]
    composed: dict[str, Path]


@pytest.fixture(scope="module")
def diamond(tmp_path_factory: pytest.TempPathFactory) -> Iterator[DiamondSetup]:
    """Compose the diamond at v1 under each view; only docs and app get v2."""
    root = tmp_path_factory.mktemp("diamond")
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
        yield DiamondSetup(releases, repos, composed)


@pytest.mark.xdist_group("views-diamond")
class TestDiamond:
    """S11: views, answers and renders of the diamond at v1."""

    def test_app_composes_its_ancestors_in_topological_order(
        self, diamond: DiamondSetup
    ) -> None:
        """S11: the resolver orders the diamond project, streamlit, docs, app."""
        assert layer_chain("app", diamond.releases["v1"]) == list(DIAMOND)

    def test_each_scoped_view_holds_its_own_and_transitive_ancestors_questions(
        self, diamond: DiamondSetup
    ) -> None:
        """S11: each layer's view adds exactly the questions of its own ancestry."""
        added = {
            layer: set(layer_view(layer, diamond.releases["v1"]).questions)
            - PROJECT_QUESTIONS
            for layer in DIAMOND
        }

        assert added == {
            "project": set(),
            "streamlit": {"container_registry"},
            "docs": {"docs_site"},
            "app": {"container_registry", "docs_site"},
        }

    def test_docs_extension_reaches_only_views_that_descend_from_docs(
        self, diamond: DiamondSetup
    ) -> None:
        """S11: the shout filter is in docs' and app's views, not the others'."""
        carries = {
            layer: SHOUT_SPEC in layer_view(layer, diamond.releases["v1"]).extensions
            for layer in DIAMOND
        }

        assert carries == {
            "project": False,
            "streamlit": False,
            "docs": True,
            "app": True,
        }

    @pytest.mark.parametrize(
        ("mode", "expected"),
        [
            pytest.param(
                "scoped",
                {
                    "project": set(),
                    "streamlit": {"container_registry"},
                    "docs": {"docs_site"},
                    "app": {"container_registry", "docs_site"},
                },
                id="scoped-records-each-view",
            ),
            pytest.param(
                "full",
                {layer: {"container_registry", "docs_site"} for layer in DIAMOND},
                id="full-records-everything-everywhere",
            ),
        ],
    )
    def test_each_answers_file_records_the_questions_of_its_view(
        self, diamond: DiamondSetup, mode: str, expected: dict[str, set[str]]
    ) -> None:
        """S11: answers files beyond the shared keys follow each layer's view."""
        recorded = {
            layer: set(recorded_answers(diamond.composed[mode], layer))
            - PROJECT_RECORDED
            for layer in DIAMOND
        }

        assert recorded == expected

    @pytest.mark.parametrize("mode", ["scoped", "full"])
    def test_descendant_files_render_through_the_ancestors_filter(
        self, diamond: DiamondSetup, mode: str
    ) -> None:
        """S11: docs' and app's files render docs_site through docs' filter."""
        rendered = {
            name: lines(diamond.composed[mode] / name) for name in DIAMOND_FILES
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


def _update_diamond(project: Path, diamond: DiamondSetup, mode: str) -> None:
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
    params=[on_own_worker(m, f"diamond-{m}") for m in ("scoped", "full")],
)
def diamond_walk(
    request: pytest.FixtureRequest,
    diamond: DiamondSetup,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[Path]:
    """Prepend a user line to both files, then update docs and app to v2."""
    mode: str = request.param
    root = tmp_path_factory.mktemp(f"diamond-{mode}")
    with temp_dir_inside(root), extensions_on_path():
        project = copy_project(diamond.composed[mode], root / "probe-app")
        make_git_project(project, diamond.repos, "v1")
        for name in DIAMOND_FILES:
            add_user_line(project / name, prepend=True)
        _update_diamond(project, diamond, mode)
        yield project


class TestDiamondUpdates:
    """S11: updating docs then app to v2."""

    def test_updates_merge_without_conflict(self, diamond_walk: Path) -> None:
        """S11: updating docs then app leaves nothing to resolve, in either view."""
        assert merge_state(diamond_walk) == CLEAN

    def test_updates_keep_the_user_line_at_the_top(self, diamond_walk: Path) -> None:
        """S11: the prepended user line stays first in both files."""
        firsts = [lines(diamond_walk / name)[0] for name in DIAMOND_FILES]

        assert firsts == [USER_LINE, USER_LINE]

    def test_docs_file_gains_the_ancestor_answer_v2_renders(
        self, diamond_walk: Path
    ) -> None:
        """S11: docs v2 renders author_name, an answer project's file records."""
        assert lines(diamond_walk / "docs/index.md")[-2:] == [
            "author=Ada Probe",
            "release=v2",
        ]

    def test_only_the_updated_layers_move_to_v2(self, diamond_walk: Path) -> None:
        """S11: docs and app record v2; project and streamlit stay at v1."""
        commits = {
            layer: answers_file(diamond_walk, layer)["_commit"] for layer in DIAMOND
        }

        assert commits == {
            "project": "v1",
            "streamlit": "v1",
            "docs": "v2",
            "app": "v2",
        }

    @pytest.mark.xdist_group("views-diamond-adjacent")
    @pytest.mark.parametrize("mode", ["scoped", "full"])
    def test_edit_beside_a_changed_line_conflicts_in_either_view(
        self, diamond: DiamondSetup, mode: str, tmp_path: Path
    ) -> None:
        """S11 run 1: a user line appended right after the line v2 rewrites conflicts.

        The conflict comes from the edit's adjacency, not the view: both views
        leave the same markers.
        """
        with extensions_on_path():
            project = copy_project(diamond.composed[mode], tmp_path / "probe-app")
            make_git_project(project, diamond.repos, "v1")
            for name in DIAMOND_FILES:
                add_user_line(project / name)
            _update_diamond(project, diamond, mode)

        assert merge_state(project).marked == sorted(DIAMOND_FILES)


# ------------------------------------------------------------------ S22

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
