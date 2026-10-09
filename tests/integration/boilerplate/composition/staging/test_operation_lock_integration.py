"""The advisory lock a mutating operation takes on its project."""

from pathlib import Path

import pytest

from boilerplate.common.exceptions import ConcurrencyContentionError
from boilerplate.composition.adding import AddRequest, LayerAdder
from boilerplate.composition.staging.operation_lock import (
    DEFAULT_LOCK_TIMEOUT,
    LOCK_TIMEOUT_ENV,
    lock_timeout,
    operation_lock,
)
from boilerplate.composition.updating import Updater
from tests.boilerplate.templates.conftest import commit_all, git


@pytest.fixture
def managed(project: Path) -> Path:
    """Return `project` with a committed ``boilerplate.lock``."""
    (project / "boilerplate.lock").write_text("placeholder\n", encoding="utf-8")
    commit_all(project, "lock")
    return project


class TestOperationLock:
    def test_second_holder_fails_with_the_concurrency_error(
        self, project: Path
    ) -> None:
        with (
            operation_lock(project, timeout=0),
            pytest.raises(ConcurrencyContentionError) as raised,
            operation_lock(project, timeout=0.1),
        ):
            pass

        assert raised.value.error_code == "BP_CONCURRENCY_CONTENTION"
        assert raised.value.retryable

    def test_lock_is_free_after_the_block(self, project: Path) -> None:
        with operation_lock(project, timeout=0):
            pass

        with operation_lock(project, timeout=0):
            pass

    def test_lock_leaves_the_working_tree_clean(self, project: Path) -> None:
        with operation_lock(project, timeout=0):
            assert git(project, "status", "--porcelain") == ""


class TestTimeout:
    def test_default_is_sixty_seconds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(LOCK_TIMEOUT_ENV, raising=False)

        assert lock_timeout() == DEFAULT_LOCK_TIMEOUT == 60.0

    def test_environment_variable_sets_it(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(LOCK_TIMEOUT_ENV, "2.5")

        assert lock_timeout() == 2.5

    @pytest.mark.parametrize("raw", ["soon", "-1", "nan"])
    def test_unusable_value_falls_back_to_the_default(
        self, monkeypatch: pytest.MonkeyPatch, raw: str
    ) -> None:
        monkeypatch.setenv(LOCK_TIMEOUT_ENV, raw)

        assert lock_timeout() == DEFAULT_LOCK_TIMEOUT


class TestMutatingOperationsTakeIt:
    def test_update_fails_while_another_operation_holds_the_project(
        self, managed: Path
    ) -> None:
        with (
            operation_lock(managed, timeout=0),
            pytest.raises(ConcurrencyContentionError),
        ):
            Updater(lock_timeout=0.1).update(managed)

    def test_update_checks_a_dirty_tree_only_inside_the_lock(
        self, managed: Path
    ) -> None:
        """Wait for the lock before the clean-tree check, as design 06 orders."""
        (managed / "notes.txt").write_text("uncommitted\n", encoding="utf-8")

        with (
            operation_lock(managed, timeout=0),
            pytest.raises(ConcurrencyContentionError),
        ):
            Updater(lock_timeout=0.1).update(managed)

    def test_add_checks_a_dirty_tree_only_inside_the_lock(self, managed: Path) -> None:
        """Wait for the lock before the clean-tree check, as design 06 orders."""
        (managed / "notes.txt").write_text("uncommitted\n", encoding="utf-8")

        with (
            operation_lock(managed, timeout=0),
            pytest.raises(ConcurrencyContentionError),
        ):
            LayerAdder(lock_timeout=0.1).add(
                managed, AddRequest(name="extra", source="unused")
            )

    def test_add_fails_while_another_operation_holds_the_project(
        self, managed: Path
    ) -> None:
        with (
            operation_lock(managed, timeout=0),
            pytest.raises(ConcurrencyContentionError),
        ):
            LayerAdder(lock_timeout=0.1).add(
                managed, AddRequest(name="extra", source="unused")
            )
