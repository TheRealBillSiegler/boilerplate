"""Tests for the version comparison a layer carries in layer_versions.py."""

from tests.boilerplate.composition.updating.versions.conftest import (
    layer,
    no_version_layer,
)


class TestDisagreesWithLock:
    """A layer disagrees only when its own recorded version differs from the lock's."""

    def test_a_layer_recorded_at_the_locks_version_agrees(self) -> None:
        assert not layer("core", "1.0.0", commit="1.0.0").disagrees_with_lock

    def test_a_layer_recorded_at_another_version_disagrees(self) -> None:
        assert layer("core", "1.0.0", commit="1.1.0").disagrees_with_lock

    def test_a_layer_whose_commit_yields_no_version_is_not_counted(self) -> None:
        assert not no_version_layer("core", "1.0.0").disagrees_with_lock
