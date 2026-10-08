"""Tests for the drift rules in drift.py."""

import pytest

from boilerplate.common.exceptions import UpdateLayerDriftError
from boilerplate.composition.updating.versions import LayerVersions, check_drift
from tests.boilerplate.composition.updating.versions.conftest import (
    layer,
    no_version_layer,
)


class TestNoDisagreement:
    """Layers that match the lock raise nothing and warn of nothing."""

    def test_returns_no_warnings(self) -> None:
        layers = (
            layer("core", "1.0.0"),
            layer("service", "1.0.0", ancestors=["core"]),
        )

        assert check_drift(layers) == ()


class TestOneLayerDisagrees:
    """A hand-run update of one layer warns and proceeds."""

    def test_warns_with_the_layer_its_commit_and_the_lock_version(self) -> None:
        layers = (
            layer("core", "1.0.0"),
            layer("service", "1.0.0", commit="1.1.0", ancestors=["core"]),
        )

        (warning,) = check_drift(layers)

        assert warning.layer == "service"
        assert warning.commit == "1.1.0"
        assert str(warning.lock_version) == "1.0.0"
        assert "service" in warning.message
        assert "1.1.0" in warning.message
        assert "1.0.0" in warning.message

    def test_an_ancestor_alone_disagreeing_warns(self) -> None:
        layers = (
            layer("core", "1.0.0", commit="2.0.0"),
            layer("service", "1.0.0", ancestors=["core"]),
        )

        assert [w.layer for w in check_drift(layers)] == ["core"]

    def test_two_unrelated_layers_disagreeing_warn_for_each(self) -> None:
        layers = (
            layer("core", "1.0.0"),
            layer("service", "1.0.0", commit="1.1.0", ancestors=["core"]),
            layer("docs", "1.0.0", commit="1.1.0", ancestors=["core"]),
        )

        assert [w.layer for w in check_drift(layers)] == ["service", "docs"]

    def test_a_commit_that_yields_no_version_is_left_to_the_downgrade_check(
        self,
    ) -> None:
        assert check_drift((no_version_layer("core", "1.0.0"),)) == ()


class TestALayerAndItsAncestorDisagree:
    """Hand-run updates of a layer and its ancestor stop the update."""

    @staticmethod
    def drifted() -> tuple[LayerVersions, ...]:
        return (
            layer("core", "1.0.0", commit="1.1.0"),
            layer("service", "1.0.0", commit="1.2.0", ancestors=["core"]),
            layer("docs", "1.0.0", ancestors=["core"]),
        )

    def test_stops(self) -> None:
        with pytest.raises(UpdateLayerDriftError):
            check_drift(self.drifted())

    def test_names_each_layers_commit_and_the_locks_version(self) -> None:
        with pytest.raises(UpdateLayerDriftError) as caught:
            check_drift(self.drifted())

        message = str(caught.value)
        assert "core" in message
        assert "service" in message
        assert "docs" not in message
        assert "1.1.0" in message
        assert "1.2.0" in message
        assert "1.0.0" in message
        assert caught.value.layers == ("core", "service")

    def test_names_the_stash_remediation(self) -> None:
        with pytest.raises(UpdateLayerDriftError) as caught:
            check_drift(self.drifted())

        assert caught.value.remediation is not None
        assert "git stash --include-untracked" in caught.value.remediation

    def test_a_transitive_ancestor_counts(self) -> None:
        layers = (
            layer("core", "1.0.0", commit="1.1.0"),
            layer("service", "1.0.0", ancestors=["core"]),
            layer("app", "1.0.0", commit="1.1.0", ancestors=["core", "service"]),
        )

        with pytest.raises(UpdateLayerDriftError):
            check_drift(layers)
