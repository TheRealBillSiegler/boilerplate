"""``ReleaseViews`` builds the views of the made-up family from release checkouts."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from boilerplate.composition.updating.release_ref import ReleaseRef
from boilerplate.composition.updating.release_views import ReleaseViews
from boilerplate.repository.release_checkouts import ReleaseCheckouts
from tests.boilerplate.templates.conftest import step_view
from tests.integration.boilerplate.composition.adding.layers import build_layer
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


class TestUpdateViewsNeedUnsafe:
    """A step is granted Copier's ``unsafe`` for what Copier's own check counts.

    Copier's ``Worker._check_unsafe`` flags the Jinja extensions of the target
    release and of the recorded one, the tasks of the recorded release, the
    tasks of the target release only when the step runs them, and the
    migrations the target release declares
    (docs/design/adr-003-permissive-execution.md). The grant follows that check
    and no more, because ``unsafe`` also switches off Copier's path-escape
    check.
    """

    @staticmethod
    def _solo(root: Path, copier: str = "") -> dict[str, ReleaseRef]:
        """Release a layer named ``solo`` that extends nothing."""
        repo = build_layer(root, "solo", extends="", copier=copier)
        return {"solo": ReleaseRef(source=repo.as_posix(), ref="1.0.0")}

    @pytest.mark.parametrize(
        ("copier", "expected"),
        [
            ("", False),
            ("_jinja_extensions:\n  - probe_ext.ProbeExtension\n", True),
            ("_jinja_extensions:\n  - _extensions/local.py:Local\n", True),
            ("_tasks:\n  - echo hi\n", True),
            ("_migrations:\n  - version: 1.0.0\n    command: echo hi\n", True),
        ],
        ids=["nothing", "importable", "own_file", "task", "migration"],
    )
    def test_follows_what_the_layer_declares(
        self, views: ReleaseViews, tmp_path: Path, copier: str, expected: bool
    ) -> None:
        releases = self._solo(tmp_path, copier)

        pair = views.update_views("solo", old=releases, target=releases)

        assert pair.needs_unsafe is expected

    def test_is_set_by_the_old_release_alone(
        self, views: ReleaseViews, tmp_path: Path
    ) -> None:
        """Copier checks the recorded release's tasks even when the target has none."""
        old = self._solo(tmp_path / "old", "_tasks:\n  - echo hi\n")
        target = self._solo(tmp_path / "target")

        pair = views.update_views("solo", old=old, target=target)

        assert pair.needs_unsafe is True

    def test_is_not_set_by_the_old_releases_migrations(
        self, views: ReleaseViews, tmp_path: Path
    ) -> None:
        """Copier reads migrations from the target release only."""
        old = self._solo(
            tmp_path / "old",
            "_migrations:\n  - version: 1.0.0\n    command: echo hi\n",
        )
        target = self._solo(tmp_path / "target")

        pair = views.update_views("solo", old=old, target=target)

        assert pair.needs_unsafe is False

    def test_a_target_task_is_a_grant_only_when_the_step_runs_it(
        self, views: ReleaseViews, tmp_path: Path
    ) -> None:
        """Copier counts the target's tasks only when the step does not skip them."""
        old = self._solo(tmp_path / "old")
        target = self._solo(tmp_path / "target", "_tasks:\n  - echo hi\n")

        pair = views.update_views("solo", old=old, target=target)

        assert (
            pair.unsafe_for(skip_tasks=True),
            pair.unsafe_for(skip_tasks=False),
        ) == (False, True)


class TestNeedsUnsafe:
    """An add copy is granted ``unsafe`` for the extensions it loads.

    The copy skips its tasks and Copier counts no migration of a copy, so only
    a Jinja extension, the view's or the layer's own, calls for the grant.
    """

    @staticmethod
    def _solo(root: Path, copier: str) -> dict[str, ReleaseRef]:
        """Release a layer named ``solo`` that extends nothing."""
        repo = build_layer(root, "solo", extends="", copier=copier)
        return {"solo": ReleaseRef(source=repo.as_posix(), ref="1.0.0")}

    @pytest.mark.parametrize(
        ("copier", "expected"),
        [
            ("", False),
            ("_jinja_extensions:\n  - probe_ext.ProbeExtension\n", True),
            ("_jinja_extensions:\n  - _extensions/local.py:Local\n", True),
            ("_tasks:\n  - echo hi\n", False),
            ("_migrations:\n  - version: 1.0.0\n    command: echo hi\n", False),
        ],
        ids=["nothing", "importable", "own_file", "task", "migration"],
    )
    def test_follows_the_extensions_the_copy_loads(
        self, views: ReleaseViews, tmp_path: Path, copier: str, expected: bool
    ) -> None:
        releases = self._solo(tmp_path, copier)

        assert views.needs_unsafe("solo", releases) is expected


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
