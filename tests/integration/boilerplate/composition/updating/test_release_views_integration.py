"""``ReleaseViews`` builds the views of the made-up family from release checkouts."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from boilerplate.composition.updating.release_ref import ReleaseRef
from boilerplate.composition.updating.release_views import ReleaseViews
from boilerplate.repository.release_checkouts import ReleaseCheckouts
from tests.boilerplate.templates.conftest import step_view
from tests.integration.boilerplate.composition.family import Family
from tests.integration.boilerplate.composition.scenarios.builders import templates_at

pytestmark = [pytest.mark.scenario]

BASE = {"core": "1.0.0", "service": "1.0.0", "docs": "1.0.0", "app": "1.0.0"}
SIBLINGS = {"core": "1.0.0", "service": "1.0.0", "docs": "1.0.0"}
LICENSE_AFTER = {**BASE, "core": "1.1.0", "app": "1.1.0"}


def releases_at(family: Family, tags: dict[str, str]) -> dict[str, ReleaseRef]:
    """Return the release of each layer at its tag in `tags`."""
    return {
        layer: ReleaseRef(source=family.repos[layer].as_posix(), ref=tag)
        for layer, tag in tags.items()
    }


@pytest.fixture
def views(tmp_path: Path) -> Iterator[ReleaseViews]:
    """Return release views rooted at ``app``, cleaned up after the test."""
    with ReleaseCheckouts() as checkouts:
        yield ReleaseViews(checkouts, workdir=tmp_path / "views")


class TestStepView:
    @pytest.mark.parametrize("layer", ["core", "service", "docs", "app"])
    def test_matches_the_view_built_from_a_templates_directory(
        self, family: Family, views: ReleaseViews, tmp_path: Path, layer: str
    ) -> None:
        """Build the same questions as the harness does from copied releases."""
        built = views.step_view(layer, releases_at(family, LICENSE_AFTER))

        expected = step_view(
            layer, "app", templates_at(family, tmp_path, LICENSE_AFTER)
        )
        assert (built.questions, built.extensions, built.declared_by) == (
            expected.questions,
            expected.extensions,
            expected.declared_by,
        )

    def test_takes_a_descendants_override_from_the_full_schema(
        self, family: Family, views: ReleaseViews
    ) -> None:
        """Give core's step the default app 1.1.0 overrides."""
        built = views.step_view("core", releases_at(family, LICENSE_AFTER))

        assert built.questions["license"]["default"] == "Apache-2.0"

    def test_scopes_the_questions_to_the_layer_and_its_ancestors(
        self, family: Family, views: ReleaseViews
    ) -> None:
        """Leave a descendant's questions out of an ancestor's step."""
        built = views.step_view("core", releases_at(family, BASE))

        assert "docs_generator" not in built.questions
        assert "project_name" in built.questions

    def test_registers_the_ancestors_extension_files_from_the_checkouts(
        self, family: Family, views: ReleaseViews
    ) -> None:
        """Point the ancestors' file-path extensions at files that exist."""
        built = views.step_view("app", releases_at(family, BASE))

        assert built.ancestor_extensions
        assert all(e.path.is_file() for e in built.ancestor_extensions)


class TestSiblingLayers:
    """Layers added one after another share no single root to compose from."""

    def test_a_layers_step_view_keeps_its_own_questions(
        self, family: Family, views: ReleaseViews
    ) -> None:
        """Define service's own question from the schema of every layer."""
        built = views.step_view("service", releases_at(family, SIBLINGS))

        assert "port" in built.questions


class TestUpdateViews:
    def test_differ_when_an_ancestor_moves(
        self, family: Family, views: ReleaseViews
    ) -> None:
        """Ask core's new ``license`` question only under the target view."""
        pair = views.update_views(
            "service",
            old=releases_at(family, BASE),
            target=releases_at(family, {**BASE, "core": "1.1.0"}),
        )

        assert (
            "license" in pair.old.questions,
            "license" in pair.target.questions,
        ) == (
            False,
            True,
        )


class TestAncestors:
    def test_lists_every_ancestor_of_each_layer(
        self, family: Family, views: ReleaseViews
    ) -> None:
        """Read the extends chains of the releases, transitively."""
        found = views.ancestors(releases_at(family, BASE))

        assert {layer: sorted(names) for layer, names in found.items()} == {
            "core": [],
            "service": ["core"],
            "docs": ["core"],
            "app": ["core", "docs", "service"],
        }


class TestTasks:
    def test_collects_the_composition_tasks_at_the_releases(
        self, family: Family, views: ReleaseViews
    ) -> None:
        """Return the accumulated task list of the full composition."""
        tasks = views.tasks(releases_at(family, BASE))

        assert len(tasks) == 2
