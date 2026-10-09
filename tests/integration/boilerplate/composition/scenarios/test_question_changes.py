"""How a layer's update handles a question its next release adds, removes or changes.

S10 adds a question an ancestor declares and a descendant overrides, under
three update mechanisms; S12 removes one; S13 retypes one; S14 renames one
behind a before-stage migration; S15 adds a validator the recorded answer
fails. S12-S15 force the scoped answers (the layer's
chain, own on top) without the update questionnaire pass, or run a vanilla
update, ``data={}``, which leaves Copier to read the layer's answers file
alone; S10b and the last S14 test add the pass. S10a, S10b and S12-S15 run on
the made-up template family; S10c stays on the bundled layers because it
needs a project composed under the full view, which the family's app cannot
render.
"""

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any, NamedTuple

import pytest

from tests.boilerplate.templates.conftest import (
    commit_all,
    compose_project,
    git,
    layer_view,
    recorded_answers,
    render_full_view,
    update_data,
    update_layer,
)
from tests.integration.boilerplate.composition.family import Family
from tests.integration.boilerplate.composition.scenarios.builders import (
    ANSWERS,
    AUTHOR,
    CLEAN,
    LICENSE_FILE,
    Recording,
    add_user_line,
    answers_file,
    append,
    build_releases,
    build_repos,
    compose_family,
    copy_project,
    license_releases,
    lines,
    make_git_project,
    merge_state,
    on_own_worker,
    recording_worker,
    temp_dir_inside,
    templates_at,
    update_family_layer,
    write,
)

BASE = {"core": "1.0.0", "service": "1.0.0", "docs": "1.0.0", "app": "1.0.0"}
LOCK_ORDER = ("core", "app")
REVERSE_ORDER = LOCK_ORDER[::-1]


def _order_id(order: tuple[str, ...]) -> str:
    return "-then-".join(order)


class Scenario(NamedTuple):
    """A scenario's working directory and its composed, git-backed project."""

    work: Path
    project: Path


class Mechanism(NamedTuple):
    """How an update builds the answers it forces (see ``update_layer``)."""

    ask_unanswered: bool = True
    data: dict[str, Any] | None = None


# The scoped data: the chain's recorded answers, no questionnaire pass.
SCOPED = Mechanism(ask_unanswered=False)
WITH_PASS = Mechanism()
VANILLA = Mechanism(data={})


def _update_in_order(
    family: Family,
    scenario: Scenario,
    order: tuple[str, ...],
    before: dict[str, str],
    after: dict[str, str],
    mechanism: Mechanism = SCOPED,
    root: str = "app",
) -> None:
    """Update each layer of `order` to its tag in `after`, committing after each.

    Args:
        family: The built family.
        scenario: The composed, git-backed project and its working directory.
        order: The layers to update, in update order.
        before: Every composed layer's tag at the recorded release.
        after: Every composed layer's tag at the target release.
        mechanism: How each update builds its forced answers.
        root: The composition's final layer.
    """
    for layer in order:
        update_family_layer(
            family,
            scenario.project,
            root=root,
            layer=layer,
            before=before,
            after=after,
            work=scenario.work,
            ask_unanswered=mechanism.ask_unanswered,
            data=mechanism.data,
        )
        commit_all(scenario.project, f"update {layer} to {after[layer]}")


def _is_clean(project: Path) -> bool:
    return git(project, "status", "--porcelain") == ""


def _compose(
    family: Family,
    work: Path,
    root: str,
    tags: dict[str, str],
    answers: dict[str, Any],
) -> Scenario:
    """Compose `root` at `tags` into a git-backed project with a user line in README."""
    project = compose_family(family, work, root, tags, answers)
    add_user_line(project / "README.md")
    return Scenario(work, project)


# ------------------------------------------------------------------ S10

LICENSE_AFTER = {**BASE, "core": "1.1.0", "app": "1.1.0"}
LICENSE_MIT = "MIT License"
LICENSE_APACHE = "Apache License, Version 2.0"


@pytest.fixture(scope="module")
def license_base(
    family: Family, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[Scenario]:
    """Compose the diamond at its first releases; core 1.1.0 adds `license`."""
    work = tmp_path_factory.mktemp("license")
    with temp_dir_inside(work):
        project = compose_family(family, work, "app", BASE, {"author_name": AUTHOR})
        yield Scenario(work, project)


# a: scoped view, no questionnaire pass; b: scoped view with the pass.
MECHANISMS = {"a": SCOPED, "b": WITH_PASS}
APACHE = {"file": LICENSE_APACHE, "core": "Apache-2.0", "app": "Apache-2.0"}
LICENSE_OUTCOMES: dict[tuple[str, tuple[str, ...]], dict[str, str]] = {
    ("a", LOCK_ORDER): {"file": LICENSE_MIT, "core": "MIT", "app": "MIT"},
    ("a", REVERSE_ORDER): {"file": LICENSE_MIT, "core": "MIT", "app": "Apache-2.0"},
    ("b", LOCK_ORDER): APACHE,
    ("b", REVERSE_ORDER): APACHE,
}


class LicenseWalk(NamedTuple):
    """A project updated to core 1.1.0 and app 1.1.0 under one mechanism and order."""

    project: Path
    key: tuple[str, tuple[str, ...]]


@pytest.fixture(
    scope="module",
    params=[
        on_own_worker((m, o), f"S10{m}-{_order_id(o)}")
        for m in MECHANISMS
        for o in (LOCK_ORDER, REVERSE_ORDER)
    ],
)
def license_walk(
    request: pytest.FixtureRequest,
    family: Family,
    license_base: Scenario,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[LicenseWalk]:
    """Update core and app to 1.1.0 under one mechanism, in one order."""
    mechanism, order = request.param
    root = tmp_path_factory.mktemp(f"S10{mechanism}")
    with temp_dir_inside(root):
        project = copy_project(license_base.project, root / "family-app")
        _update_in_order(
            family,
            Scenario(license_base.work, project),
            order,
            BASE,
            LICENSE_AFTER,
            MECHANISMS[mechanism],
        )
        yield LicenseWalk(project, (mechanism, order))


class TestAddedQuestionWithOverride:
    """S10: core 1.1.0 adds `license` (MIT); app 1.1.0 overrides it (Apache-2.0)."""

    def test_update_merges_without_conflict(self, license_walk: LicenseWalk) -> None:
        """S10: every mechanism and order updates cleanly."""
        assert merge_state(license_walk.project) == CLEAN

    def test_override_reaches_only_the_layers_its_mechanism_lets_it(
        self, license_walk: LicenseWalk
    ) -> None:
        """S10: without the update questionnaire pass the override is lost.

        S10a: core's scoped view sees only MIT, so core's file and answers
        record MIT, and app inherits MIT from core's answers when it updates
        second. S10b: the pass over the full view answers Apache-2.0 for every
        layer in either order.
        """
        project = license_walk.project
        state = {
            "file": lines(project / "LICENSE")[0],
            "core": recorded_answers(project, "core")["license"],
            "app": recorded_answers(project, "app")["license"],
        }

        assert state == LICENSE_OUTCOMES[license_walk.key]

    def test_questionnaire_pass_answers_the_new_question_with_the_override(
        self, family: Family, license_base: Scenario
    ) -> None:
        """S10b: the pass at the target gives core's update the descendant's default."""
        data = update_data(
            license_base.project,
            root="app",
            layer="core",
            templates_dir=templates_at(family, license_base.work, LICENSE_AFTER),
        )

        assert data["license"] == "Apache-2.0"


# S10c composes under the full view, which renders app's files without docs'
# filter and so cannot run on the family: it stays on the bundled layers, where
# project v4 adds `license` and streamlit v4 overrides it.
FULL_ORDERS = (("project", "streamlit"), ("streamlit", "project"))
FULL_APACHE = {
    "file": "license=Apache-2.0",
    "project": "Apache-2.0",
    "streamlit": "Apache-2.0",
}


class FullViewBase(NamedTuple):
    """The bundled license releases, repositories and a v1 project composed whole."""

    releases: dict[str, Path]
    repos: dict[str, Path]
    project: Path


@pytest.fixture(scope="module")
def full_view_base(tmp_path_factory: pytest.TempPathFactory) -> Iterator[FullViewBase]:
    """Compose v1 of the bundled layers under the full view and commit it."""
    root = tmp_path_factory.mktemp("license-full")
    with temp_dir_inside(root):
        releases = build_releases(
            root, ("v1", "v4"), license_releases, merge_readme=False
        )
        repos = build_repos(root, releases)
        project = root / "composed" / "full" / "probe-app"
        render_full_view(
            "streamlit", project, context_data=ANSWERS, templates_dir=releases["v1"]
        )
        make_git_project(project, repos, "v1")
        yield FullViewBase(releases, repos, project)


@pytest.fixture(
    scope="module",
    params=[on_own_worker(o, f"S10c-{_order_id(o)}") for o in FULL_ORDERS],
)
def full_view_walk(
    request: pytest.FixtureRequest,
    full_view_base: FullViewBase,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[Path]:
    """Update both bundled layers to v4 under the full view, in one order."""
    order: tuple[str, ...] = request.param
    root = tmp_path_factory.mktemp("S10c")
    with temp_dir_inside(root):
        project = copy_project(full_view_base.project, root / "probe-app")
        for layer in order:
            update_layer(
                project,
                root="streamlit",
                layer=layer,
                source=full_view_base.repos[layer],
                ref="v4",
                templates=full_view_base.releases,
                full_view=True,
                ask_unanswered=False,
            )
            commit_all(project, f"update {layer} to v4")
        yield project


class TestAddedQuestionUnderTheFullView:
    """S10c: the full view sees the override without a questionnaire pass."""

    def test_update_merges_without_conflict(self, full_view_walk: Path) -> None:
        """S10c: both orders update cleanly."""
        assert merge_state(full_view_walk) == CLEAN

    def test_override_reaches_every_layer(self, full_view_walk: Path) -> None:
        """S10c: the file and both answers files take Apache-2.0 in either order."""
        state = {
            "file": lines(full_view_walk / LICENSE_FILE)[0],
            "project": recorded_answers(full_view_walk, "project")["license"],
            "streamlit": recorded_answers(full_view_walk, "streamlit")["license"],
        }

        assert state == FULL_APACHE


# ------------------------------------------------------------------ S12

REMOVAL_FILE = "tests/test_smoke.py"
REMOVAL_BEFORE = {"core": "2.1.0", "service": "1.0.0"}
REMOVAL_AFTER = {"core": "3.0.0", "service": "1.0.0"}


class RemovedQuestion(NamedTuple):
    """Core updated 2.1.0 to 3.0.0 with its chain's answers forced."""

    project: Path
    recording: Recording


@pytest.fixture(scope="module")
def removed(
    family: Family, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[RemovedQuestion]:
    """Compose with `use_tests` off at core 2.1.0, then update core to 3.0.0."""
    work = tmp_path_factory.mktemp("removed")
    with temp_dir_inside(work):
        project = compose_family(
            family, work, "service", REMOVAL_BEFORE, {"use_tests": False}
        )
        worker, recording = recording_worker([REMOVAL_FILE])
        update_family_layer(
            family,
            project,
            root="service",
            layer="core",
            before=REMOVAL_BEFORE,
            after=REMOVAL_AFTER,
            work=work,
            ask_unanswered=False,
            worker_type=worker,
        )
        yield RemovedQuestion(project, recording)


@pytest.mark.xdist_group("S12")
class TestRemovedQuestion:
    """S12: core 3.0.0 drops the `use_tests` question its 2.1.0 paths used."""

    def test_views_differ_by_the_removed_question(
        self, family: Family, tmp_path: Path
    ) -> None:
        """S12: core's 2.1.0 view asks `use_tests`; its 3.0.0 view does not."""
        asks = {
            tag: "use_tests"
            in layer_view(
                "core", templates_at(family, tmp_path, {"core": tag})
            ).questions
            for tag in ("2.1.0", "3.0.0")
        }

        assert asks == {"2.1.0": True, "3.0.0": False}

    def test_old_copy_renders_the_recorded_answer(
        self, removed: RemovedQuestion
    ) -> None:
        """S12: the old copy omits the smoke test that `use_tests: false` drops."""
        assert removed.recording.copies["old_copy"][REMOVAL_FILE] is None

    def test_project_file_moves_to_the_new_release(
        self, removed: RemovedQuestion
    ) -> None:
        """S12: the update applies 3.0.0's unconditional smoke test."""
        assert lines(removed.project / REMOVAL_FILE)[0] == (
            '"""Smoke test for family_app."""'
        )

    def test_answers_file_drops_the_removed_question(
        self, removed: RemovedQuestion
    ) -> None:
        """S12: core records 3.0.0 without `use_tests`, though data passed it."""
        recorded = answers_file(removed.project, "core")

        assert (recorded["_commit"], "use_tests" in recorded) == ("3.0.0", False)

    def test_descendant_answers_file_keeps_the_answer(
        self, removed: RemovedQuestion
    ) -> None:
        """S12: service, not yet updated, still records `use_tests` at 1.0.0."""
        recorded = answers_file(removed.project, "service")

        assert (recorded["_commit"], recorded["use_tests"]) == ("1.0.0", False)

    def test_update_merges_without_conflict(self, removed: RemovedQuestion) -> None:
        """S12: removing a question the old paths used merges cleanly."""
        assert merge_state(removed.project) == CLEAN


# ------------------------------------------------------------------ S13


class RetypeCase(NamedTuple):
    """One S13 scenario: what is composed, what a release changes, what it rejects.

    Attributes:
        root: The composition's final layer.
        before: Every composed layer's tag at the recorded release.
        after: Every composed layer's tag at the target release.
        answers: The recorded answer the next release cannot take.
        owner: The layer that declares the changed question.
        descendant: A layer whose answers file records the question too.
        rejection: The error a forced update of either raises, if any.
    """

    root: str
    before: dict[str, str]
    after: dict[str, str]
    answers: dict[str, Any]
    owner: str
    descendant: str
    rejection: str | None


# service 1.1.0 retypes `port` from str to int; core 2.1.0 drops python 3.11.
RETYPE_CASES = {
    "retype_bad": RetypeCase(
        "app",
        BASE,
        {**BASE, "core": "1.1.0", "service": "1.1.0", "app": "1.1.0"},
        {"port": "eighty"},
        "service",
        "app",
        "invalid literal for int() with base 10: 'eighty'",
    ),
    "retype_ok": RetypeCase(
        "app",
        BASE,
        {**BASE, "core": "1.1.0", "service": "1.1.0", "app": "1.1.0"},
        {"port": "8080"},
        "service",
        "app",
        None,
    ),
    "choice_lost": RetypeCase(
        "service",
        {"core": "2.0.0", "service": "1.0.0"},
        {"core": "2.1.0", "service": "1.1.0"},
        {"python_version": "3.11", "maintainer_name": AUTHOR},
        "core",
        "service",
        "Invalid choice for 'python_version': '3.11' is not in ['3.12', '3.13']",
    ),
}
REJECTED = [c for c, case in RETYPE_CASES.items() if case.rejection]
# Core 2.1.0 ships a before-stage migration that rewrites a recorded 3.11
# before the forced answer is rejected, so only the retype leaves the project
# untouched; the narrowed-choice claim stays on the bundled layers below.
UNTOUCHED = ["retype_bad"]
# Copier prints this hint only when Git rejects the negative --inter-hunk-context
# it tries first, as Git 2.55 and later do; a Git that accepts it prints nothing.
# The silent-replacement tests drop this line and assert nothing else is on stderr.
GIT_HINT = "Make sure Git >= 2.24 is installed to improve updates."


def _retype_case(case: str) -> object:
    return on_own_worker(case, f"S13-{case}")


class Retyped(NamedTuple):
    """One S13 case, composed at its recorded release."""

    case: RetypeCase
    scenario: Scenario


@pytest.fixture(scope="module")
def retyped(
    request: pytest.FixtureRequest,
    family: Family,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[Retyped]:
    """Compose one S13 case with its recorded answer."""
    name: str = request.param
    case = RETYPE_CASES[name]
    work = tmp_path_factory.mktemp(name)
    with temp_dir_inside(work):
        yield Retyped(
            case, _compose(family, work, case.root, case.before, case.answers)
        )


class TestRetypedQuestion:
    """S13: service 1.1.0 retypes `port`; core 2.1.0 drops a Python choice."""

    @pytest.mark.parametrize("which", ["owner", "descendant"])
    @pytest.mark.parametrize(
        "retyped", [_retype_case(c) for c in REJECTED], indirect=True
    )
    def test_forced_answer_the_new_release_cannot_parse_fails_the_update(
        self, family: Family, retyped: Retyped, which: str, tmp_path: Path
    ) -> None:
        """S13: forcing the recorded answer raises Copier's raw ValueError.

        The descendant's update fails the same way: its answers file records
        the owner's question too.
        """
        case, scenario = retyped
        assert case.rejection is not None
        project = copy_project(scenario.project, tmp_path / "family-app")

        with pytest.raises(ValueError, match=re.escape(case.rejection)):
            update_family_layer(
                family,
                project,
                root=case.root,
                layer=getattr(case, which),
                before=case.before,
                after=case.after,
                work=scenario.work,
                ask_unanswered=False,
            )

    @pytest.mark.parametrize(
        "retyped", [_retype_case(c) for c in UNTOUCHED], indirect=True
    )
    def test_rejected_update_leaves_the_project_untouched(
        self, family: Family, retyped: Retyped, tmp_path: Path
    ) -> None:
        """S13: the rejection comes before any render; tree and answers stay put."""
        case, scenario = retyped
        assert case.rejection is not None
        project = copy_project(scenario.project, tmp_path / "family-app")
        with pytest.raises(ValueError, match=re.escape(case.rejection)):
            update_family_layer(
                family,
                project,
                root=case.root,
                layer=case.owner,
                before=case.before,
                after=case.after,
                work=scenario.work,
                ask_unanswered=False,
            )

        assert (
            _is_clean(project),
            answers_file(project, case.owner)["_commit"],
        ) == (True, case.before[case.owner])

    @pytest.mark.parametrize("retyped", [_retype_case("retype_ok")], indirect=True)
    def test_castable_answer_carries_over_as_the_new_type(
        self, family: Family, retyped: Retyped, tmp_path: Path
    ) -> None:
        """S13: a recorded "8080" becomes the int 8080 in the answers files."""
        case, scenario = retyped
        project = copy_project(scenario.project, tmp_path / "family-app")
        _update_in_order(
            family,
            Scenario(scenario.work, project),
            (case.owner, case.descendant),
            case.before,
            case.after,
        )

        assert {
            layer: recorded_answers(project, layer)["port"]
            for layer in (case.owner, case.descendant)
        } == {"service": 8080, "app": 8080}

    @pytest.mark.parametrize("retyped", [_retype_case("retype_bad")], indirect=True)
    def test_vanilla_update_silently_replaces_an_unparseable_answer(
        self,
        family: Family,
        retyped: Retyped,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """S13: with data={} Copier drops the last answer and takes the new default.

        No exception, and stderr carries nothing but Copier's Git hint, which
        Git 2.55 and later trigger: eighty becomes 8000.
        """
        case, scenario = retyped
        project = copy_project(scenario.project, tmp_path / "family-app")
        capsys.readouterr()
        update_family_layer(
            family,
            project,
            root=case.root,
            layer=case.owner,
            before=case.before,
            after=case.after,
            work=scenario.work,
            data={},
        )

        assert (
            [
                line
                for line in lines(project / "Dockerfile")
                if line.startswith("EXPOSE")
            ],
            [line for line in capsys.readouterr().err.splitlines() if line != GIT_HINT],
        ) == (["EXPOSE 8000"], [])


def _narrowed_choices(ref: str, release: Path) -> None:
    """Narrow project's `license` choices in v2 and render the answer."""
    options = "[MIT, Apache-2.0, GPL-3.0]" if ref == "v1" else "[MIT, Apache-2.0]"
    append(
        release / "project" / "copier.yml",
        f'\nlicense:\n  type: str\n  help: "License"\n  choices: {options}\n'
        "  default: MIT\n",
    )
    write(release / "project" / "settings.txt.jinja", "license={{ license }}\n")


NARROWED_REJECTION = (
    "Invalid choice for 'license': 'GPL-3.0' is not in ['MIT', 'Apache-2.0']"
)


class Narrowed(NamedTuple):
    """The bundled layers composed at v1 recording a license v2 no longer offers."""

    releases: dict[str, Path]
    repos: dict[str, Path]
    project: Path


@pytest.fixture(scope="module")
def narrowed(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Narrowed]:
    """Compose the bundled layers at v1 with the GPL-3.0 license recorded."""
    root = tmp_path_factory.mktemp("narrowed")
    with temp_dir_inside(root):
        releases = build_releases(root, ("v1", "v2"), _narrowed_choices)
        repos = build_repos(root, releases)
        project = root / "composed" / "probe-app"
        compose_project(
            "streamlit", project, {**ANSWERS, "license": "GPL-3.0"}, releases["v1"]
        )
        make_git_project(project, repos, "v1")
        add_user_line(project / "README.md")
        yield Narrowed(releases, repos, project)


def _update_narrowed(
    narrowed: Narrowed,
    project: Path,
    *,
    ask_unanswered: bool = True,
    data: dict[str, Any] | None = None,
) -> None:
    update_layer(
        project,
        root="streamlit",
        layer="project",
        source=narrowed.repos["project"],
        ref="v2",
        templates=narrowed.releases,
        ask_unanswered=ask_unanswered,
        data=data,
    )


@pytest.mark.xdist_group("S13-narrowed")
class TestNarrowedChoiceOnTheBundledLayers:
    """S13: project v2 drops a `license` choice, with no migration for the answer."""

    def test_rejected_update_leaves_the_project_untouched(
        self, narrowed: Narrowed, tmp_path: Path
    ) -> None:
        """S13: the rejection comes before any render; tree and answers stay at v1."""
        project = copy_project(narrowed.project, tmp_path / "probe-app")
        with pytest.raises(ValueError, match=re.escape(NARROWED_REJECTION)):
            _update_narrowed(narrowed, project, ask_unanswered=False)

        assert (_is_clean(project), answers_file(project, "project")["_commit"]) == (
            True,
            "v1",
        )

    def test_vanilla_update_silently_replaces_the_lost_choice(
        self,
        narrowed: Narrowed,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """S13: with data={} Copier drops the last answer and takes the default.

        No exception, and stderr carries nothing but Copier's Git hint, which
        Git 2.55 and later trigger: GPL-3.0 becomes MIT.
        """
        project = copy_project(narrowed.project, tmp_path / "probe-app")
        capsys.readouterr()
        _update_narrowed(narrowed, project, data={})

        assert (
            lines(project / "settings.txt"),
            [line for line in capsys.readouterr().err.splitlines() if line != GIT_HINT],
        ) == (["license=MIT"], [])


# ------------------------------------------------------------------ S14

RENAME_BEFORE = {"core": "1.0.0", "service": "1.0.0"}
RENAME_AFTER = {"core": "2.0.0", "service": "1.1.0"}
RENAME_ORDERS = (("core", "service"), ("service", "core"))
RENAME_OUTCOMES: dict[tuple[str, ...], dict[str, str]] = {
    ("core", "service"): {"core": AUTHOR, "service": AUTHOR},
    ("service", "core"): {"core": AUTHOR, "service": "Your Name"},
}


def _rename_case(order: tuple[str, ...]) -> object:
    return on_own_worker(order, f"S14-{_order_id(order)}")


ALL_RENAME_CASES = [_rename_case(o) for o in RENAME_ORDERS]


@pytest.fixture(scope="module")
def renamed(
    request: pytest.FixtureRequest,
    family: Family,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[tuple[tuple[str, ...], Path]]:
    """Compose core and service, then update both to their next releases."""
    order: tuple[str, ...] = request.param
    work = tmp_path_factory.mktemp(f"S14-{_order_id(order)}")
    with temp_dir_inside(work):
        scenario = _compose(
            family, work, "service", RENAME_BEFORE, {"author_name": AUTHOR}
        )
        _update_in_order(
            family, scenario, order, RENAME_BEFORE, RENAME_AFTER, root="service"
        )
        yield order, scenario.project


class TestRenamedQuestion:
    """S14: core 2.0.0 renames author_name to maintainer_name behind a migration."""

    @pytest.mark.parametrize("renamed", ALL_RENAME_CASES, indirect=True)
    def test_renamed_answer_reaches_the_layers_the_migration_reaches(
        self, renamed: tuple[tuple[str, ...], Path]
    ) -> None:
        """S14: a layer updated before any answers file is migrated records the default.

        In reverse order, with only core shipping the migration, service's
        update finds no maintainer_name anywhere and records 'Your Name'. Lock
        order carries 'Ada Probe'.
        """
        order, project = renamed
        recorded = {
            layer: recorded_answers(project, layer)["maintainer_name"]
            for layer in ("core", "service")
        }

        assert recorded == RENAME_OUTCOMES[order]

    @pytest.mark.parametrize("renamed", ALL_RENAME_CASES, indirect=True)
    def test_rename_merges_without_conflict(
        self, renamed: tuple[tuple[str, ...], Path]
    ) -> None:
        """S14: both orders update without a conflict."""
        assert merge_state(renamed[1]) == CLEAN

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "The update questionnaire pass reads the answers files before the "
            "migration runs and forces the renamed question's default over the "
            "migrated answer; design 06 (Step 4: Three-Way Merge) expects "
            "migrations to carry recorded answers through."
        ),
    )
    @pytest.mark.parametrize("order", RENAME_ORDERS, ids=_order_id)
    def test_update_questionnaire_pass_keeps_the_migrated_answer(
        self, family: Family, order: tuple[str, ...], tmp_path: Path
    ) -> None:
        """S14 with the pass: both layers record and render the migrated answer."""
        scenario = _compose(
            family, tmp_path, "service", RENAME_BEFORE, {"author_name": AUTHOR}
        )
        _update_in_order(
            family,
            scenario,
            order,
            RENAME_BEFORE,
            RENAME_AFTER,
            WITH_PASS,
            root="service",
        )
        recorded = {
            layer: recorded_answers(scenario.project, layer)["maintainer_name"]
            for layer in ("core", "service")
        }
        byline = lines(scenario.project / "README.md")[2]

        assert (recorded, byline) == (
            {"core": AUTHOR, "service": AUTHOR},
            f"A Python 3.12 project by {AUTHOR}.",
        )


# ------------------------------------------------------------------ S15

SITE_NAME_ERROR = (
    "Validation error for question 'docs_site_name': The site name cannot be empty."
)
TIGHTENED_AFTER = {**BASE, "core": "1.1.0", "docs": "1.1.0", "app": "1.1.0"}


@pytest.fixture(scope="module")
def tightened(
    family: Family, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[Scenario]:
    """Compose recording an empty site name, which docs 1.1.0's validator rejects."""
    work = tmp_path_factory.mktemp("tightened")
    with temp_dir_inside(work):
        yield _compose(family, work, "app", BASE, {"docs_site_name": ""})


class TestTightenedValidator:
    """S15: docs 1.1.0 requires a non-empty `docs_site_name`."""

    @pytest.mark.parametrize("layer", ["docs", "app"])
    def test_forced_answer_the_validator_rejects_fails_the_update(
        self, family: Family, tightened: Scenario, layer: str, tmp_path: Path
    ) -> None:
        """S15: forcing the recorded empty name fails validation before any render."""
        project = copy_project(tightened.project, tmp_path / "family-app")

        with pytest.raises(ValueError, match=re.escape(SITE_NAME_ERROR)):
            update_family_layer(
                family,
                project,
                root="app",
                layer=layer,
                before=BASE,
                after=TIGHTENED_AFTER,
                work=tightened.work,
                ask_unanswered=False,
            )

    def test_vanilla_update_silently_swaps_in_a_valid_default(
        self, family: Family, tightened: Scenario, tmp_path: Path
    ) -> None:
        """S15: with data={} and a valid default, the recorded empty name is replaced.

        Both answers files and the docs index end up with the default name.
        """
        project = copy_project(tightened.project, tmp_path / "family-app")
        _update_in_order(
            family,
            Scenario(tightened.work, project),
            ("docs", "app"),
            BASE,
            TIGHTENED_AFTER,
            VANILLA,
        )
        names = {
            layer: recorded_answers(project, layer)["docs_site_name"]
            for layer in ("docs", "app")
        }
        names["docs/index.md"] = lines(project / "docs" / "index.md")[2]

        assert names == {
            "docs": "Family App documentation",
            "app": "Family App documentation",
            "docs/index.md": "Welcome to Family App documentation, built with mkdocs.",
        }
