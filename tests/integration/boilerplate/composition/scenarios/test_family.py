"""Smoke tests for the made-up template family the composition scenarios run on.

Every layer's every release must be a valid Copier template, and the first
release of each layer must compose into the shapes the scenarios build on. The
expected file sets and values come from the family's specification, not from
rendering the templates. Updates across releases are the settlement scenarios'
business and are not tested here.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

import pytest
from packaging.version import Version

from boilerplate.integrations.copier_types import Template
from boilerplate.models.template_meta import TemplateMeta
from tests.boilerplate.templates.conftest import compose_project, git
from tests.integration.boilerplate.composition.family import (
    Family,
    assemble_templates_dir,
    family_versions,
)
from tests.integration.boilerplate.composition.scenarios.builders import (
    answers_file,
    make_git_project,
    on_own_worker,
    tree,
)
from tests.integration.boilerplate.composition.temp_dir import temp_dir_inside

ANSWERS = {"project_name": "Family App"}
LAYERS = ("core", "service", "docs", "ci", "app")
RELEASES = [
    pytest.param(layer, version, id=f"{layer}-{version}")
    for layer, versions in family_versions().items()
    for version in versions
]
# What a layer's first release declares, from the family's specification.
FIRST_RELEASE_QUESTIONS = {
    "core": {
        "project_name",
        "package_name",
        "author_name",
        "python_version",
        "use_tests",
        "api_token",
    },
    "service": {"python_version", "port"},
    "docs": {"docs_generator", "docs_site_name"},
    "ci": {"ci_provider"},
    "app": set(),
}

CORE_FILES = {
    ".gitignore",
    "CHANGELOG.md",
    "README.md",
    "pyproject.toml",
    "src/family_app/__init__.py",
    "tests/test_smoke.py",
    ".copier-answers.core.yml",
}
SERVICE_FILES = {"Dockerfile", "SERVICE.md", ".copier-answers.service.yml"}
DOCS_FILES = {"mkdocs.yml", "docs/index.md", ".copier-answers.docs.yml"}
CI_FILES = {".github/workflows/ci.yml", ".copier-answers.ci.yml"}
APP_FILES = {"src/family_app/app.py", "APP.md", ".copier-answers.app.yml"}
# Shape name -> (the composition's final layer, the files it writes).
SHAPES = {
    "core-alone": ("core", CORE_FILES),
    "core-service": ("service", CORE_FILES | SERVICE_FILES),
    "core-ci": ("ci", CORE_FILES | CI_FILES),
    "core-docs": ("docs", CORE_FILES | DOCS_FILES),
    "diamond": ("app", CORE_FILES | SERVICE_FILES | DOCS_FILES | APP_FILES),
}
# Choice -> (the question it answers, the final layer, its file, the rival file).
CHOICES = {
    "mkdocs": ("docs_generator", "docs", "mkdocs.yml", "docs/conf.py"),
    "sphinx": ("docs_generator", "docs", "docs/conf.py", "mkdocs.yml"),
    "github": (
        "ci_provider",
        "ci",
        ".github/workflows/ci.yml",
        ".gitlab-ci.yml",
    ),
    "gitlab": (
        "ci_provider",
        "ci",
        ".gitlab-ci.yml",
        ".github/workflows/ci.yml",
    ),
}


class Composed(NamedTuple):
    """A project composed from the first release of every layer.

    Attributes:
        project: The composed project's directory.
        files: The text of every file in it, keyed by POSIX path.
    """

    project: Path
    files: dict[str, str]


def _compose(
    family: Family,
    root: str,
    work: Path,
    answers: dict[str, object] | None = None,
    *,
    skip_tasks: bool = True,
    tags: dict[str, str] | None = None,
) -> Composed:
    """Compose `root` into `work`, each layer at its first release unless `tags` says.

    Args:
        family: The built family.
        root: The composition's final layer.
        work: The scenario's working directory.
        answers: Answers forced into the questionnaire, beside the project name.
        skip_tasks: Whether to skip the merged post-generation tasks.
        tags: Tags to use instead of a layer's first release, keyed by layer.
    """
    templates = assemble_templates_dir(
        family,
        work / "templates",
        {**{k: v[0] for k, v in family.tags.items()}, **(tags or {})},
    )
    project = work / "project"
    compose_project(
        root,
        project,
        {**ANSWERS, **(answers or {})},
        templates,
        skip_tasks=skip_tasks,
    )
    return Composed(project, tree(project))


@pytest.fixture(scope="module", params=[on_own_worker(s, s) for s in SHAPES])
def shape(
    request: pytest.FixtureRequest,
    family: Family,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[tuple[str, Composed]]:
    """Compose one shape at the first release of each layer."""
    name: str = request.param
    work = tmp_path_factory.mktemp(name)
    with temp_dir_inside(work):
        yield name, _compose(family, SHAPES[name][0], work)


@pytest.fixture(scope="module", params=[on_own_worker(c, c) for c in CHOICES])
def choice(
    request: pytest.FixtureRequest,
    family: Family,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[tuple[str, Composed]]:
    """Compose the docs or ci layer with one generator or provider chosen."""
    name: str = request.param
    question, root, _, _ = CHOICES[name]
    work = tmp_path_factory.mktemp(name)
    with temp_dir_inside(work):
        yield name, _compose(family, root, work, {question: name})


@pytest.fixture(scope="module")
def diamond(
    family: Family, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[Composed]:
    """Compose the diamond: core, service, docs and app."""
    work = tmp_path_factory.mktemp("diamond-only")
    with temp_dir_inside(work):
        yield _compose(family, "app", work)


@pytest.fixture(scope="module")
def core_alone(
    family: Family, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[Composed]:
    """Compose core on its own."""
    work = tmp_path_factory.mktemp("core-only")
    with temp_dir_inside(work):
        yield _compose(family, "core", work)


@pytest.fixture(scope="module")
def tasked(
    family: Family, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[Composed]:
    """Compose the diamond with tasks enabled."""
    work = tmp_path_factory.mktemp("tasked")
    with temp_dir_inside(work):
        yield _compose(family, "app", work, skip_tasks=False)


LICENSED_VERSIONS = [
    version
    for version in family_versions()["core"]
    if Version(version) >= Version("1.1.0")
]
LICENSE_FILE_NAME = "LICENSE"


@pytest.fixture(
    scope="module",
    params=[
        on_own_worker((version, choice), f"license-{version}-{choice}")
        for version in LICENSED_VERSIONS
        for choice in ("MIT", "None")
    ],
)
def licensed(
    request: pytest.FixtureRequest,
    family: Family,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[tuple[str, Composed]]:
    """Compose core at one release from 1.1.0 on with one license choice made."""
    version, choice = request.param
    work = tmp_path_factory.mktemp(f"license-{version}-{choice}")
    with temp_dir_inside(work):
        yield (
            choice,
            _compose(family, "core", work, {"license": choice}, tags={"core": version}),
        )


@pytest.fixture(scope="module")
def mixed_project(
    family: Family, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[Path]:
    """Compose service over core 1.1.0, whose layers sit at different tags."""
    work = tmp_path_factory.mktemp("mixed-tags")
    with temp_dir_inside(work):
        composed = _compose(
            family, "service", work, tags={"core": "1.1.0", "service": "1.0.0"}
        )
        make_git_project(
            composed.project, family.repos, {"core": "1.1.0", "service": "1.0.0"}
        )
        yield composed.project


class TestFamilyBuilder:
    """The builder turns the stored versions into tagged repositories."""

    @pytest.mark.parametrize(
        ("layer", "expected"),
        [
            ("core", ["1.0.0", "1.1.0", "2.0.0", "2.1.0", "3.0.0"]),
            ("service", ["1.0.0", "1.1.0", "1.2.0"]),
            ("docs", ["1.0.0", "1.1.0", "1.2.0"]),
            ("ci", ["1.0.0", "1.1.0", "1.2.0", "1.3.0"]),
            ("app", ["1.0.0", "1.1.0"]),
        ],
    )
    def test_each_layer_is_tagged_at_its_releases_oldest_first(
        self, family: Family, layer: str, expected: list[str]
    ) -> None:
        """Tag every release of a layer in release order."""
        assert family.tags[layer] == expected
        assert git(family.repos[layer], "tag", "--sort=creatordate").split() == expected

    def test_a_later_release_drops_the_paths_it_lists(self, family: Family) -> None:
        """Remove the conditional smoke test path at core 3.0.0."""
        listed = git(family.repos["core"], "ls-tree", "-r", "--name-only", "3.0.0")

        assert "{% if use_tests %}" not in listed

    def test_a_later_release_keeps_the_files_it_leaves_alone(
        self, family: Family
    ) -> None:
        """Carry core 1.0.0's README forward to core 3.0.0."""
        listed = git(family.repos["core"], "ls-tree", "-r", "--name-only", "3.0.0")

        assert "README.md.jinja" in listed.splitlines()

    def test_no_release_ships_the_deletion_list(self, family: Family) -> None:
        """Keep the deletion list out of the committed release."""
        listed = git(family.repos["core"], "ls-tree", "-r", "--name-only", "3.0.0")

        assert "_deleted.txt" not in listed


class TestGitProject:
    """A composed project records the tag each layer's render matches."""

    @pytest.mark.parametrize(
        ("layer", "tag"), [("core", "1.1.0"), ("service", "1.0.0")]
    )
    def test_each_answers_file_records_its_own_layers_tag(
        self, mixed_project: Path, layer: str, tag: str
    ) -> None:
        """Record the tag given for the layer, not one shared by all."""
        assert answers_file(mixed_project, layer)["_commit"] == tag

    @pytest.mark.parametrize("layer", ["core", "service"])
    def test_each_answers_file_points_at_its_layers_repository(
        self, family: Family, mixed_project: Path, layer: str
    ) -> None:
        """Point the answers file at the layer's own repository."""
        recorded = answers_file(mixed_project, layer)["_src_path"]

        assert Path(recorded) == family.repos[layer]

    def test_a_layer_the_project_lacks_is_left_out(self, mixed_project: Path) -> None:
        """Write no answers file for a layer that was not composed."""
        assert sorted(p.name for p in mixed_project.glob(".copier-answers.*.yml")) == [
            ".copier-answers.core.yml",
            ".copier-answers.service.yml",
        ]


class TestEveryRelease:
    """Every layer's every release is a valid Copier template."""

    @pytest.mark.parametrize(("layer", "version"), RELEASES)
    def test_questions_parse(self, family: Family, layer: str, version: str) -> None:
        """Parse the questions of a tagged release."""
        template = Template(url=str(family.repos[layer]), ref=version)
        try:
            assert isinstance(template.questions_data, dict)
        finally:
            template._cleanup()  # pyright: ignore[reportPrivateUsage]

    @pytest.mark.parametrize(("layer", "version"), RELEASES)
    def test_metadata_names_its_layer_and_tag(
        self, family: Family, layer: str, version: str
    ) -> None:
        """Declare the layer's own name and the tag's version in boilerplate.yml."""
        meta = TemplateMeta.load(family.releases[layer][version])

        assert (meta.name, meta.version) == (layer, Version(version))

    @pytest.mark.parametrize("layer", LAYERS)
    def test_first_release_declares_the_specified_questions(
        self, family: Family, layer: str
    ) -> None:
        """Declare exactly the questions the specification gives the first release."""
        template = Template(url=str(family.releases[layer]["1.0.0"]))

        assert set(template.questions_data) == FIRST_RELEASE_QUESTIONS[layer]


class TestComposedShapes:
    """The first releases compose into the shapes the scenarios build on."""

    def test_renders_the_expected_files(self, shape: tuple[str, Composed]) -> None:
        """Write exactly the files the shape's layers ship."""
        name, composed = shape

        assert set(composed.files) == SHAPES[name][1]

    def test_leaves_no_unrendered_template_syntax(
        self, shape: tuple[str, Composed]
    ) -> None:
        """Render every `{{` and `{%` away."""
        _, composed = shape

        assert [
            path
            for path, text in composed.files.items()
            if "{{" in text or "{%" in text
        ] == []


class TestConditionalPaths:
    """Each choice renders only its own files."""

    def test_renders_the_chosen_file_and_not_its_rival(
        self, choice: tuple[str, Composed]
    ) -> None:
        """Render the chosen alternative's file and leave its rival out."""
        name, composed = choice
        _, _, own, rival = CHOICES[name]

        assert (own in composed.files, rival in composed.files) == (True, False)


class TestLicenseChoice:
    """Core's license question has an off choice from 1.1.0 on."""

    @pytest.mark.parametrize("version", LICENSED_VERSIONS)
    def test_offers_none_beside_the_licenses(
        self, family: Family, version: str
    ) -> None:
        """List `None` among the license choices of every release that asks."""
        template = Template(url=str(family.releases["core"][version]))

        assert template.questions_data["license"]["choices"] == [
            "MIT",
            "Apache-2.0",
            "None",
        ]

    def test_chosen_license_writes_the_license_file(
        self, licensed: tuple[str, Composed]
    ) -> None:
        """Write a LICENSE only for a choice other than `None`."""
        choice, composed = licensed

        assert (LICENSE_FILE_NAME in composed.files) == (choice != "None")


class TestOverridesAndHooks:
    """The layer mechanics the family exists to exercise reach rendered output."""

    def test_service_overrides_cores_python_version_default(
        self, diamond: Composed
    ) -> None:
        """Default the Python version to 3.13 where service is composed."""
        assert "FROM python:3.13-slim" in diamond.files["Dockerfile"].splitlines()

    def test_core_keeps_its_own_python_version_default_without_service(
        self, core_alone: Composed
    ) -> None:
        """Default the Python version to 3.12 when service is not composed."""
        assert 'requires-python = ">=3.12"' in core_alone.files["pyproject.toml"]

    def test_service_context_hook_variable_reaches_the_dockerfile(
        self, diamond: Composed
    ) -> None:
        """Render the container user only the service layer's hook defines."""
        assert "USER service" in diamond.files["Dockerfile"].splitlines()

    def test_secret_answer_stays_out_of_the_answers_file(
        self, shape: tuple[str, Composed]
    ) -> None:
        """Keep the secret `api_token` out of core's answers file."""
        _, composed = shape

        assert "api_token" not in composed.files[".copier-answers.core.yml"]

    def test_core_declares_its_changelog_project_owned(self, family: Family) -> None:
        """List the changelog under core's `_skip_if_exists`."""
        template = Template(url=str(family.releases["core"]["1.0.0"]))

        assert template.skip_if_exists == ["CHANGELOG.md"]


class TestAppUsesDocsFilter:
    """App renders through the filter docs ships."""

    def test_app_guide_links_to_the_docs_heading_anchor(
        self, diamond: Composed
    ) -> None:
        """Turn the project name "Family App" into the anchor `family-app`."""
        assert "(docs/index.md#family-app)" in diamond.files["APP.md"]

    def test_app_module_docstring_points_at_the_same_anchor(
        self, diamond: Composed
    ) -> None:
        """Render the same anchor in the application module."""
        assert "docs/index.md#family-app" in diamond.files["src/family_app/app.py"]


class TestDocsFilterRelease:
    """Docs 1.2.0 changes only what the ``docs_anchor`` filter returns."""

    @pytest.fixture(scope="class")
    def diamond_on_new_docs(
        self, family: Family, tmp_path_factory: pytest.TempPathFactory
    ) -> Iterator[Composed]:
        """Compose the diamond with docs at 1.2.0 and every other layer at its first."""
        work = tmp_path_factory.mktemp("diamond-docs-1-2-0")
        with temp_dir_inside(work):
            yield _compose(family, "app", work, tags={"docs": "1.2.0"})

    def test_app_guide_links_to_the_new_anchor_spelling(
        self, diamond_on_new_docs: Composed
    ) -> None:
        """Join the words of "Family App" with an underscore, not a hyphen."""
        assert "(docs/index.md#family_app)" in diamond_on_new_docs.files["APP.md"]

    def test_release_changes_only_the_filter_and_its_version(
        self, family: Family
    ) -> None:
        """Leave every other file of docs 1.1.0 as it was."""
        old = family.releases["docs"]["1.1.0"]
        new = family.releases["docs"]["1.2.0"]
        changed = {
            path.relative_to(new).as_posix()
            for path in new.rglob("*")
            if path.is_file()
            and (
                not (old / path.relative_to(new)).exists()
                or path.read_bytes() != (old / path.relative_to(new)).read_bytes()
            )
        }

        assert changed == {"_extensions/docfilters.py", "boilerplate.yml"}


class TestServiceMaintainerRelease:
    """Service 1.2.0 adds a line that renders core's ``maintainer_name``."""

    MAINTAINER = "Ada Probe"

    @pytest.fixture(scope="class")
    def service_on_new_core(
        self, family: Family, tmp_path_factory: pytest.TempPathFactory
    ) -> Iterator[Composed]:
        """Compose service 1.2.0 over core 2.0.0, which renamed the question."""
        work = tmp_path_factory.mktemp("service-1-2-0")
        with temp_dir_inside(work):
            yield _compose(
                family,
                "service",
                work,
                {"maintainer_name": self.MAINTAINER},
                tags={"core": "2.0.0", "service": "1.2.0"},
            )

    def test_service_guide_names_the_maintainer(
        self, service_on_new_core: Composed
    ) -> None:
        """Render core's ``maintainer_name`` into the service guide."""
        assert (
            f"Maintained by {self.MAINTAINER}."
            in service_on_new_core.files["SERVICE.md"].splitlines()
        )

    def test_release_changes_only_the_guide_and_its_version(
        self, family: Family
    ) -> None:
        """Leave every other file of service 1.1.0 as it was."""
        old = family.releases["service"]["1.1.0"]
        new = family.releases["service"]["1.2.0"]
        changed = {
            path.relative_to(new).as_posix()
            for path in new.rglob("*")
            if path.is_file()
            and (
                not (old / path.relative_to(new)).exists()
                or path.read_bytes() != (old / path.relative_to(new)).read_bytes()
            )
        }

        assert changed == {"SERVICE.md.jinja", "boilerplate.yml"}


class TestCoreTask:
    """Core's task runs at compose."""

    def test_task_writes_its_marker_once_across_the_diamond(
        self, tasked: Composed
    ) -> None:
        """Append one line to the marker although five layers render."""
        marker = tasked.project / ".core-task-marker"

        assert marker.read_text(encoding="utf-8").splitlines() == ["core task ran"]
