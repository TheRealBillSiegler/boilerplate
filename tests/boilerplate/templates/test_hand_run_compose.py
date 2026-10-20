"""A by-hand compose of `project` then `streamlit` renders what `new` renders.

The documented by-hand compose (docs/templates-hub/plain-copier.md) is two
``copier copy`` commands; these tests mirror them through ``copier.run_copy``,
Copier's public API, not the command line. `project` runs first with
streamlit's two overrides; `README.md` is removed because streamlit lists it in
``_skip_if_exists``; `streamlit` then runs with ``--overwrite``, `project`'s
answers file as ``--data-file`` and the two computed values (``project_slug``,
``package_name``) passed explicitly. The reference is
``boilerplate new streamlit`` from the same answers (ADR-015 points 1 and 4).
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from copier import run_copy

from tests.boilerplate.templates.conftest import TEMPLATES, render_project
from tests.integration.boilerplate.composition.scenarios.builders import tree
from tests.integration.boilerplate.composition.temp_dir import temp_dir_inside

ANSWERS: dict[str, Any] = {
    "project_name": "Probe App",
    "description": "Probe description",
    "author_name": "Ada Probe",
    "author_email": "ada@example.com",
}
# Streamlit's overrides of `project`'s defaults; `new` hands them to both layers.
OVERRIDES: dict[str, Any] = {
    "dependencies": ["streamlit", "pydantic>=2"],
    "sample_module": False,
}
# Literals, not recomputed: `project_name` "Probe App" slugifies to "probe-app".
DERIVED: dict[str, str] = {"project_slug": "probe-app", "package_name": "probe_app"}
PROJECT_ANSWERS = ".copier-answers.project.yml"
STREAMLIT_ANSWERS = ".copier-answers.streamlit.yml"
# Files that legitimately differ: Boilerplate's lock and the per-layer answers files.
EXCLUDED = {"boilerplate.lock", PROJECT_ANSWERS, STREAMLIT_ANSWERS}


def _hand_compose(dest: Path, *, derived: dict[str, str]) -> None:
    """Mirror the two documented ``copier copy`` commands through ``run_copy``."""
    run_copy(
        str(TEMPLATES / "project"),
        dest,
        data={**ANSWERS, **OVERRIDES},
        defaults=True,
        unsafe=True,
        quiet=True,
        skip_tasks=True,
    )
    (dest / "README.md").unlink()
    data_file = yaml.safe_load((dest / PROJECT_ANSWERS).read_text(encoding="utf-8"))
    run_copy(
        str(TEMPLATES / "streamlit"),
        dest,
        data={**data_file, **derived},
        defaults=True,
        overwrite=True,
        unsafe=True,
        quiet=True,
        skip_tasks=True,
    )


def _files(root: Path) -> dict[str, str]:
    return {k: v for k, v in tree(root).items() if Path(k).name not in EXCLUDED}


@pytest.fixture(scope="module")
def projects(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[Path, Path]]:
    """Return the by-hand project and the `new` project from one answer set."""
    root = tmp_path_factory.mktemp("hand-run")
    by_hand, via_new = root / "probe-app", root / "probe-app-new"
    with temp_dir_inside(root):
        _hand_compose(by_hand, derived=DERIVED)
        render_project("streamlit", via_new, context_data=ANSWERS)
        yield by_hand, via_new


class TestByHandComposeRendersWhatNewRenders:
    """Seam: Copier's public API over the bundled folders; truth: `boilerplate new`."""

    def test_rendered_files_match_new_except_lock_and_answers_files(
        self, projects: tuple[Path, Path]
    ) -> None:
        by_hand, via_new = projects

        assert _files(by_hand) == _files(via_new)

    def test_omitting_the_derived_values_silently_drops_the_package_files(
        self, projects: tuple[Path, Path], tmp_path: Path
    ) -> None:
        """Without the derived values, no file under a package path renders.

        Copier skips a path whose templated segment renders empty and raises
        nothing, so the omission shows only as missing files.
        """
        by_hand, _ = projects
        bare = tmp_path / "probe-app"
        with temp_dir_inside(tmp_path):
            _hand_compose(bare, derived={})

        by_hand_files = _files(by_hand)
        streamlit_package_files = {
            path for path in by_hand_files if "probe_app" in path
        } - {  # project's own, rendered in its run
            "src/probe_app/__init__.py",
            "tests/probe_app/test_import.py",
        }
        assert set(by_hand_files) - set(_files(bare)) == streamlit_package_files


def _recorded_keys(project: Path, name: str) -> set[str]:
    return set(yaml.safe_load((project / name).read_text(encoding="utf-8")))


class TestByHandAnswersFilesRecordOnlyTheLayersOwnQuestions:
    """ADR-015 point 4: a layer records the questions its `copier.yml` declares.

    Seam: the answers files Copier writes; truth: streamlit's `copier.yml`,
    which declares `dependencies`, `sample_module` and `container_registry`.
    """

    def test_by_hand_streamlit_records_its_three_questions(
        self, projects: tuple[Path, Path]
    ) -> None:
        by_hand, _ = projects

        assert _recorded_keys(by_hand, STREAMLIT_ANSWERS) == {
            "_src_path",
            "container_registry",
            "dependencies",
            "sample_module",
        }

    def test_new_records_projects_questions_in_streamlits_file_as_well(
        self, projects: tuple[Path, Path]
    ) -> None:
        by_hand, via_new = projects

        assert _recorded_keys(via_new, STREAMLIT_ANSWERS) - _recorded_keys(
            by_hand, STREAMLIT_ANSWERS
        ) == {
            "author_email",
            "author_name",
            "build_backend",
            "dev_dependencies",
            "description",
            "package_index_url",
            "project_name",
        }

    def test_projects_answers_file_is_the_same_either_way(
        self, projects: tuple[Path, Path]
    ) -> None:
        by_hand, via_new = projects

        assert _recorded_keys(by_hand, PROJECT_ANSWERS) == _recorded_keys(
            via_new, PROJECT_ANSWERS
        )
