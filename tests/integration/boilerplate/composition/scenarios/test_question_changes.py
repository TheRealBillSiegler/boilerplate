"""How a layer's update handles a question its next release adds, removes or changes.

S10 adds a question an ancestor declares and a descendant overrides, under
three update mechanisms; S12 removes one; S13 retypes one; S14 renames one
behind a before-stage migration; S15 adds a validator the recorded answer
fails. As in the probes, S12-S15 force the scoped answers (the layer's
chain, own on top) without the update questionnaire pass, or run a vanilla
update, ``data={}``, which leaves Copier to read the layer's answers file
alone; S10b and the last S14 test add the pass.
"""

import re
from collections.abc import Callable, Iterator
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
from tests.integration.boilerplate.composition.scenarios.builders import (
    ANSWERS,
    CLEAN,
    LICENSE_FILE,
    LICENSE_TAGS,
    LicenseProject,
    Recording,
    add_user_line,
    answers_file,
    append,
    build_releases,
    build_repos,
    compose_license_project,
    copy_project,
    license_releases,
    lines,
    make_git_project,
    merge_state,
    on_own_worker,
    recording_worker,
    substitute,
    temp_dir_inside,
    write,
)

LAYERS = ("project", "streamlit")
LOCK_ORDER = LAYERS
REVERSE_ORDER = LAYERS[::-1]


def _order_id(order: tuple[str, ...]) -> str:
    return "-then-".join(order)


class Mechanism(NamedTuple):
    """How an update builds the answers it forces (see ``update_layer``)."""

    full_view: bool = False
    ask_unanswered: bool = True
    data: dict[str, Any] | None = None


# The probes' scoped data: the chain's recorded answers, no questionnaire pass.
SCOPED = Mechanism(ask_unanswered=False)
WITH_PASS = Mechanism()
VANILLA = Mechanism(data={})


def _update_in_order(
    project: Path,
    order: tuple[str, ...],
    sources: tuple[dict[str, Path], dict[str, Path]],
    ref: str,
    mechanism: Mechanism = SCOPED,
) -> None:
    """Update each layer of `order` to `ref`, committing after each.

    Args:
        project: The composed, git-backed project.
        order: The layers to update, in update order.
        sources: The releases and the layer repositories, each keyed as
            ``update_layer`` takes them.
        ref: The target release.
        mechanism: How each update builds its forced answers.
    """
    releases, repos = sources
    for layer in order:
        update_layer(
            project,
            root="streamlit",
            layer=layer,
            source=repos[layer],
            ref=ref,
            templates=releases,
            full_view=mechanism.full_view,
            ask_unanswered=mechanism.ask_unanswered,
            data=mechanism.data,
        )
        commit_all(project, f"update {layer} to {ref}")


def _is_clean(project: Path) -> bool:
    return git(project, "status", "--porcelain") == ""


# ------------------------------------------------------------------ S10


class LicenseBases(NamedTuple):
    """The S10 releases and repositories, and v1 composes under each view."""

    releases: dict[str, Path]
    repos: dict[str, Path]
    composed: dict[str, Path]


@pytest.fixture(scope="module")
def license_bases(tmp_path_factory: pytest.TempPathFactory) -> Iterator[LicenseBases]:
    """Compose v1 under each view; v4 adds `license`, streamlit v4 overrides it."""
    root = tmp_path_factory.mktemp("license")
    with temp_dir_inside(root):
        releases = build_releases(
            root, ("v1", "v4", "v5"), license_releases, merge_readme=False
        )
        repos = build_repos(root, releases, LICENSE_TAGS)
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
        for project in composed.values():
            make_git_project(project, repos, "v1")
        yield LicenseBases(releases, repos, composed)


# a: scoped view, no questionnaire pass; b: scoped view with the pass;
# c: full view, every answers file forced, no pass.
MECHANISMS = {
    "a": SCOPED,
    "b": WITH_PASS,
    "c": Mechanism(full_view=True, ask_unanswered=False),
}
APACHE = {
    "file": "license=Apache-2.0",
    "project": "Apache-2.0",
    "streamlit": "Apache-2.0",
}
LICENSE_OUTCOMES: dict[tuple[str, tuple[str, ...]], dict[str, str]] = {
    ("a", LOCK_ORDER): {"file": "license=MIT", "project": "MIT", "streamlit": "MIT"},
    ("a", REVERSE_ORDER): {
        "file": "license=MIT",
        "project": "MIT",
        "streamlit": "Apache-2.0",
    },
    ("b", LOCK_ORDER): APACHE,
    ("b", REVERSE_ORDER): APACHE,
    ("c", LOCK_ORDER): APACHE,
    ("c", REVERSE_ORDER): APACHE,
}


class LicenseWalk(NamedTuple):
    """A project updated to v4 under one mechanism and order."""

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
    license_bases: LicenseBases,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[LicenseWalk]:
    """Update both layers v1 to v4 under one mechanism, in one order."""
    mechanism, order = request.param
    view = "full" if MECHANISMS[mechanism].full_view else "scoped"
    root = tmp_path_factory.mktemp(f"S10{mechanism}")
    with temp_dir_inside(root):
        project = copy_project(license_bases.composed[view], root / "probe-app")
        releases = {r: license_bases.releases[r] for r in ("v1", "v4")}
        _update_in_order(
            project,
            order,
            (releases, license_bases.repos),
            "v4",
            MECHANISMS[mechanism],
        )
        yield LicenseWalk(project, (mechanism, order))


class TestAddedQuestionWithOverride:
    """S10: project v4 adds `license` (MIT); streamlit v4 overrides it (Apache-2.0)."""

    def test_update_merges_without_conflict(self, license_walk: LicenseWalk) -> None:
        """S10: every mechanism and order updates cleanly."""
        assert merge_state(license_walk.project) == CLEAN

    def test_override_reaches_only_the_layers_its_mechanism_lets_it(
        self, license_walk: LicenseWalk
    ) -> None:
        """S10: without the update questionnaire pass the override is lost.

        S10a: project's scoped view sees only MIT, so project's file and
        answers record MIT, and streamlit inherits MIT from project's answers
        when it updates second. S10b: the pass over the full view answers
        Apache-2.0 for every layer in either order. S10c: the full view sees
        the override directly.
        """
        project = license_walk.project
        state = {
            "file": lines(project / LICENSE_FILE)[0],
            "project": recorded_answers(project, "project")["license"],
            "streamlit": recorded_answers(project, "streamlit")["license"],
        }

        assert state == LICENSE_OUTCOMES[license_walk.key]

    def test_questionnaire_pass_answers_the_new_question_with_the_override(
        self, license_bases: LicenseBases
    ) -> None:
        """S10b: the pass at v4 gives project's update the descendant's default."""
        data = update_data(
            license_bases.composed["scoped"],
            root="streamlit",
            layer="project",
            templates_dir=license_bases.releases["v4"],
        )

        assert data["license"] == "Apache-2.0"


# ------------------------------------------------------------------ S12


class RemovedQuestion(NamedTuple):
    """Project updated v4 to v5 with its chain's answers forced."""

    setup: LicenseProject
    recording: Recording


@pytest.fixture(scope="module")
def removed(tmp_path_factory: pytest.TempPathFactory) -> Iterator[RemovedQuestion]:
    """Compose at v4 (license recorded), then update project to v5 (license gone)."""
    root = tmp_path_factory.mktemp("removed")
    with temp_dir_inside(root):
        setup = compose_license_project(root)
        worker, recording = recording_worker([LICENSE_FILE])
        update_layer(
            setup.project,
            root="streamlit",
            layer="project",
            source=setup.repos["project"],
            ref="v5",
            templates={r: setup.releases[r] for r in ("v4", "v5")},
            ask_unanswered=False,
            worker_type=worker,
        )
        yield RemovedQuestion(setup, recording)


@pytest.mark.xdist_group("S12")
class TestRemovedQuestion:
    """S12: project v5 drops the `license` question its v4 file rendered."""

    def test_views_differ_by_the_removed_question(
        self, removed: RemovedQuestion
    ) -> None:
        """S12: project's v4 view asks `license`; its v5 view does not."""
        asks = {
            ref: "license"
            in layer_view("project", removed.setup.releases[ref]).questions
            for ref in ("v4", "v5")
        }

        assert asks == {"v4": True, "v5": False}

    def test_old_copy_renders_the_recorded_answer(
        self, removed: RemovedQuestion
    ) -> None:
        """S12: the old copy renders v4's file with the recorded Apache-2.0."""
        assert removed.recording.copies["old_copy"][LICENSE_FILE] == (
            "license=Apache-2.0\nrelease=v4\n"
        )

    def test_project_file_moves_to_the_new_release(
        self, removed: RemovedQuestion
    ) -> None:
        """S12: the update applies v5's file text."""
        assert lines(removed.setup.project / LICENSE_FILE) == [
            "license=(question removed in v5)",
            "release=v5",
        ]

    def test_answers_file_drops_the_removed_question(
        self, removed: RemovedQuestion
    ) -> None:
        """S12: project records v5 without `license`, though data passed it."""
        recorded = answers_file(removed.setup.project, "project")

        assert (recorded["_commit"], "license" in recorded) == ("v5", False)

    def test_descendant_answers_file_keeps_the_answer(
        self, removed: RemovedQuestion
    ) -> None:
        """S12: streamlit, not yet updated, still records license at v4."""
        recorded = answers_file(removed.setup.project, "streamlit")

        assert (recorded["_commit"], recorded["license"]) == ("v4", "Apache-2.0")

    def test_update_merges_without_conflict(self, removed: RemovedQuestion) -> None:
        """S12: removing a question the old file used merges cleanly."""
        assert merge_state(removed.setup.project) == CLEAN


# ------------------------------------------------------------------ S13


def _retyped_port(ref: str, release: Path) -> None:
    kind, default = ("str", '"8080"') if ref == "v1" else ("int", "8080")
    append(
        release / "project" / "copier.yml",
        f'\nport:\n  type: {kind}\n  help: "Port"\n  default: {default}\n',
    )
    write(
        release / "project" / "settings.txt.jinja",
        "port={{ port }}\nport_is_number={{ port is number }}\n",
    )


def _narrowed_choices(ref: str, release: Path) -> None:
    options = "[MIT, Apache-2.0, GPL-3.0]" if ref == "v1" else "[MIT, Apache-2.0]"
    append(
        release / "project" / "copier.yml",
        f'\nlicense:\n  type: str\n  help: "License"\n  choices: {options}\n'
        "  default: MIT\n",
    )
    write(release / "project" / "settings.txt.jinja", "license={{ license }}\n")


RETYPE_CASES: dict[str, tuple[Callable[[str, Path], None], dict[str, Any]]] = {
    "retype_bad": (_retyped_port, {"port": "eighty"}),
    "retype_ok": (_retyped_port, {"port": "8080"}),
    "choice_lost": (_narrowed_choices, {"license": "GPL-3.0"}),
}


class Composed(NamedTuple):
    """A scenario's releases, repositories and git-backed v1 project."""

    releases: dict[str, Path]
    repos: dict[str, Path]
    project: Path


def _compose_v1(
    root: Path, mutate: Callable[[str, Path], None], answers: dict[str, Any]
) -> Composed:
    releases = build_releases(root, ("v1", "v2"), mutate)
    repos = build_repos(root, releases)
    project = root / "composed" / "probe-app"
    compose_project("streamlit", project, answers, releases["v1"])
    make_git_project(project, repos, "v1")
    add_user_line(project / "README.md")
    return Composed(releases, repos, project)


def _retype_case(case: str) -> object:
    return on_own_worker(case, f"S13-{case}")


@pytest.fixture(scope="module")
def retyped(
    request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[tuple[str, Composed]]:
    """Compose v1 with one S13 case's recorded answer."""
    case: str = request.param
    mutate, extra = RETYPE_CASES[case]
    root = tmp_path_factory.mktemp(case)
    with temp_dir_inside(root):
        yield case, _compose_v1(root, mutate, {**ANSWERS, **extra})


REJECTIONS = {
    "retype_bad": "invalid literal for int() with base 10: 'eighty'",
    "choice_lost": "Invalid choice for 'license': 'GPL-3.0' is not in ['MIT', 'Apache-2.0']",
}
# Every update here, clean ones included, prints this hint; Git 2.55 rejects the
# negative --inter-hunk-context Copier tries first.
GIT_HINT = "Make sure Git >= 2.24 is installed to improve updates."
VANILLA_REPLACEMENTS = {
    "retype_bad": ["port=8080", "port_is_number=True"],
    "choice_lost": ["license=MIT"],
}


class TestRetypedQuestion:
    """S13: project v2 retypes `port` (str to int) or drops a `license` choice."""

    @pytest.mark.parametrize("layer", LAYERS)
    @pytest.mark.parametrize(
        "retyped", [_retype_case(c) for c in REJECTIONS], indirect=True
    )
    def test_forced_answer_the_new_release_cannot_parse_fails_the_update(
        self, retyped: tuple[str, Composed], layer: str, tmp_path: Path
    ) -> None:
        """S13: forcing the recorded answer raises Copier's raw ValueError.

        Streamlit's update fails the same way: its answers file records the
        ancestor's question too.
        """
        case, composed = retyped
        project = copy_project(composed.project, tmp_path / "probe-app")

        with pytest.raises(ValueError, match=re.escape(REJECTIONS[case])):
            update_layer(
                project,
                root="streamlit",
                layer=layer,
                source=composed.repos[layer],
                ref="v2",
                templates=composed.releases,
                ask_unanswered=False,
            )

    @pytest.mark.parametrize(
        "retyped", [_retype_case(c) for c in REJECTIONS], indirect=True
    )
    def test_rejected_update_leaves_the_project_untouched(
        self, retyped: tuple[str, Composed], tmp_path: Path
    ) -> None:
        """S13: the rejection comes before any render; tree and answers stay at v1."""
        case, composed = retyped
        project = copy_project(composed.project, tmp_path / "probe-app")
        with pytest.raises(ValueError, match=re.escape(REJECTIONS[case])):
            update_layer(
                project,
                root="streamlit",
                layer="project",
                source=composed.repos["project"],
                ref="v2",
                templates=composed.releases,
                ask_unanswered=False,
            )

        assert (_is_clean(project), answers_file(project, "project")["_commit"]) == (
            True,
            "v1",
        )

    @pytest.mark.parametrize("retyped", [_retype_case("retype_ok")], indirect=True)
    def test_castable_answer_carries_over_as_the_new_type(
        self, retyped: tuple[str, Composed], tmp_path: Path
    ) -> None:
        """S13: a recorded "8080" becomes the int 8080 in files and answers."""
        _, composed = retyped
        project = copy_project(composed.project, tmp_path / "probe-app")
        _update_in_order(
            project,
            LOCK_ORDER,
            (composed.releases, composed.repos),
            "v2",
        )

        assert (
            lines(project / "settings.txt"),
            recorded_answers(project, "streamlit")["port"],
        ) == (["port=8080", "port_is_number=True"], 8080)

    @pytest.mark.parametrize(
        "retyped", [_retype_case(c) for c in VANILLA_REPLACEMENTS], indirect=True
    )
    def test_vanilla_update_silently_replaces_an_unparseable_answer(
        self,
        retyped: tuple[str, Composed],
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """S13: with data={} Copier drops the last answer and takes the new default.

        No exception, and stderr carries only the hint every update prints:
        eighty becomes 8080, GPL-3.0 becomes MIT.
        """
        case, composed = retyped
        project = copy_project(composed.project, tmp_path / "probe-app")
        capsys.readouterr()
        update_layer(
            project,
            root="streamlit",
            layer="project",
            source=composed.repos["project"],
            ref="v2",
            templates=composed.releases,
            data={},
        )

        assert (
            lines(project / "settings.txt"),
            capsys.readouterr().err.splitlines(),
        ) == (VANILLA_REPLACEMENTS[case], [GIT_HINT])


# ------------------------------------------------------------------ S14

RENAME_MIGRATION = """
_migrations:
  - when: "{{ _stage == 'before' }}"
    command:
      - "{{ _copier_python }}"
      - -c
      - |
        import pathlib, re, sys
        p = pathlib.Path(sys.argv[1])
        t = p.read_text(encoding="utf-8")
        n = re.sub(r"(?m)^author_name:", "maintainer_name:", t)
        p.write_text(n, encoding="utf-8", newline="\\n")
      - "{{ _copier_conf.answers_file }}"
"""


def _renamed_author(streamlit_migrates: bool) -> Callable[[str, Path], None]:
    """Rename author_name to maintainer_name in v2, migrating project's answers."""

    def mutate(ref: str, release: Path) -> None:
        if ref == "v1":
            return
        project, streamlit = release / "project", release / "streamlit"
        substitute(project / "copier.yml", "author_name:\n", "maintainer_name:\n")
        append(project / "copier.yml", RENAME_MIGRATION)
        for path in (
            project / "README.md.jinja",
            project / "pyproject.toml.jinja",
            streamlit / "README.md.jinja",
        ):
            substitute(path, "{{ author_name }}", "{{ maintainer_name }}")
        if streamlit_migrates:
            # streamlit already declares `_migrations`; add a second entry.
            append(
                streamlit / "copier.yml", RENAME_MIGRATION.split("_migrations:\n")[1]
            )

    return mutate


RENAME_CASES = {"project_only_migrates": False, "both_migrate": True}
ADA = {"project": "Ada Probe", "streamlit": "Ada Probe"}
RENAME_OUTCOMES: dict[tuple[str, tuple[str, ...]], dict[str, str]] = {
    ("project_only_migrates", LOCK_ORDER): ADA,
    ("project_only_migrates", REVERSE_ORDER): {
        "project": "Ada Probe",
        "streamlit": "Your Name",
    },
    ("both_migrate", LOCK_ORDER): ADA,
    ("both_migrate", REVERSE_ORDER): ADA,
}


def _rename_case(case: str, order: tuple[str, ...]) -> object:
    return on_own_worker((case, order), f"S14-{case}-{_order_id(order)}")


ALL_RENAME_CASES = [_rename_case(c, o) for c, o in RENAME_OUTCOMES]


@pytest.fixture(scope="module")
def renamed(
    request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[tuple[tuple[str, tuple[str, ...]], Path]]:
    """Compose v1, then update both layers to v2 in one order."""
    case, order = request.param
    root = tmp_path_factory.mktemp(case)
    with temp_dir_inside(root):
        composed = _compose_v1(root, _renamed_author(RENAME_CASES[case]), dict(ANSWERS))
        _update_in_order(
            composed.project,
            order,
            (composed.releases, composed.repos),
            "v2",
        )
        yield (case, order), composed.project


class TestRenamedQuestion:
    """S14: project v2 renames author_name to maintainer_name behind a migration."""

    @pytest.mark.parametrize("renamed", ALL_RENAME_CASES, indirect=True)
    def test_renamed_answer_reaches_the_layers_the_migration_reaches(
        self, renamed: tuple[tuple[str, tuple[str, ...]], Path]
    ) -> None:
        """S14: a layer updated before any answers file is migrated records the default.

        In reverse order with only project shipping the migration, streamlit's
        update finds no maintainer_name anywhere and records 'Your Name'.
        Lock order, or the migration in both layers, carries 'Ada Probe'.
        """
        key, project = renamed
        recorded = {
            layer: recorded_answers(project, layer)["maintainer_name"]
            for layer in LAYERS
        }

        assert recorded == RENAME_OUTCOMES[key]

    @pytest.mark.parametrize(
        "renamed",
        [_rename_case("project_only_migrates", REVERSE_ORDER)],
        indirect=True,
    )
    def test_unmigrated_reverse_order_renders_the_default_into_the_readme(
        self, renamed: tuple[tuple[str, tuple[str, ...]], Path]
    ) -> None:
        """S14: the lost answer reaches the README and stays after project's update."""
        _, project = renamed
        maintainer = [line for line in lines(project / "README.md") if "@" in line]

        assert maintainer == [
            "Your Name <ada@example.com>. Send questions and changes there."
        ]

    @pytest.mark.parametrize("renamed", ALL_RENAME_CASES, indirect=True)
    def test_rename_merges_without_conflict(
        self, renamed: tuple[tuple[str, tuple[str, ...]], Path]
    ) -> None:
        """S14: every case and order updates without a conflict."""
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
    @pytest.mark.parametrize("order", [LOCK_ORDER, REVERSE_ORDER], ids=_order_id)
    def test_update_questionnaire_pass_keeps_the_migrated_answer(
        self, order: tuple[str, ...], tmp_path: Path
    ) -> None:
        """S14 with the pass: both layers record and render the migrated answer."""
        composed = _compose_v1(
            tmp_path, _renamed_author(RENAME_CASES["both_migrate"]), dict(ANSWERS)
        )
        _update_in_order(
            composed.project,
            order,
            (composed.releases, composed.repos),
            "v2",
            WITH_PASS,
        )
        recorded = {
            layer: recorded_answers(composed.project, layer)["maintainer_name"]
            for layer in LAYERS
        }
        maintainer = [
            line for line in lines(composed.project / "README.md") if "@" in line
        ]

        assert (recorded, maintainer) == (
            ADA,
            ["Ada Probe <ada@example.com>. Send questions and changes there."],
        )


# ------------------------------------------------------------------ S15

CORP_VALIDATOR = (
    "\"{% if not author_email.endswith('@corp.example') %}"
    'must be a corp.example address{% endif %}"'
)
VALIDATION_ERROR = (
    "Validation error for question 'author_email': must be a corp.example address"
)


def _tightened_email(new_default: bool) -> Callable[[str, Path], None]:
    """Add a validator in v2 the recorded email fails, optionally a valid default."""

    def mutate(ref: str, release: Path) -> None:
        if ref == "v1":
            return
        default = "dev@corp.example" if new_default else "username@domain.com"
        substitute(
            release / "project" / "copier.yml",
            '  default: "username@domain.com"\n',
            f'  default: "{default}"\n  validator: {CORP_VALIDATOR}\n',
        )

    return mutate


VALIDATOR_CASES = {"default_unchanged": False, "default_now_valid": True}


def _validator_case(case: str) -> object:
    return on_own_worker(case, f"S15-{case}")


@pytest.fixture(scope="module")
def tightened(
    request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[tuple[str, Composed]]:
    """Compose v1 recording ada@example.com, which v2's validator rejects."""
    case: str = request.param
    root = tmp_path_factory.mktemp(case)
    with temp_dir_inside(root):
        mutate = _tightened_email(VALIDATOR_CASES[case])
        yield case, _compose_v1(root, mutate, dict(ANSWERS))


class TestTightenedValidator:
    """S15: project v2 requires a corp.example author_email."""

    @pytest.mark.parametrize("layer", LAYERS)
    @pytest.mark.parametrize(
        "tightened", [_validator_case(c) for c in VALIDATOR_CASES], indirect=True
    )
    def test_forced_answer_the_validator_rejects_fails_the_update(
        self, tightened: tuple[str, Composed], layer: str, tmp_path: Path
    ) -> None:
        """S15: forcing the recorded email fails validation before any render."""
        _, composed = tightened
        project = copy_project(composed.project, tmp_path / "probe-app")

        with pytest.raises(ValueError, match=re.escape(VALIDATION_ERROR)):
            update_layer(
                project,
                root="streamlit",
                layer=layer,
                source=composed.repos[layer],
                ref="v2",
                templates=composed.releases,
                ask_unanswered=False,
            )

    @pytest.mark.parametrize(
        "tightened", [_validator_case("default_unchanged")], indirect=True
    )
    def test_vanilla_update_fails_when_the_default_is_invalid_too(
        self, tightened: tuple[str, Composed], tmp_path: Path
    ) -> None:
        """S15: with data={} the answer is dropped and the old default fails too."""
        _, composed = tightened
        project = copy_project(composed.project, tmp_path / "probe-app")

        with pytest.raises(ValueError, match=re.escape(VALIDATION_ERROR)):
            update_layer(
                project,
                root="streamlit",
                layer="project",
                source=composed.repos["project"],
                ref="v2",
                templates=composed.releases,
                data={},
            )

    @pytest.mark.parametrize(
        "tightened", [_validator_case("default_now_valid")], indirect=True
    )
    def test_vanilla_update_silently_swaps_in_a_valid_default(
        self, tightened: tuple[str, Composed], tmp_path: Path
    ) -> None:
        """S15: with data={} and a valid default, the recorded email is replaced.

        Both answers files and pyproject.toml end up with dev@corp.example.
        """
        _, composed = tightened
        project = copy_project(composed.project, tmp_path / "probe-app")
        _update_in_order(
            project,
            LOCK_ORDER,
            (composed.releases, composed.repos),
            "v2",
            VANILLA,
        )
        emails = {
            layer: recorded_answers(project, layer)["author_email"] for layer in LAYERS
        }
        emails["pyproject.toml"] = next(
            line for line in lines(project / "pyproject.toml") if "email" in line
        )

        assert emails == {
            "project": "dev@corp.example",
            "streamlit": "dev@corp.example",
            "pyproject.toml": 'authors = [{ name = "Ada Probe", email = "dev@corp.example" }]',
        }
