"""Tests for the version resolution that runs before any layer does."""

import pytest

from boilerplate.common.exceptions import UpdateDowngradeError, UpdateLayerDriftError
from boilerplate.composition.updating.versions import (
    LayerVersions,
    ResumePlan,
    resolve_versions,
)
from boilerplate.types import SerializableVersion
from tests.boilerplate.composition.updating.versions.conftest import layer, v

TARGETS = {"core": "2.0.0", "service": "1.0.0", "app": "1.1.0"}


def _layers(
    *, core: str = "1.0.0", service: str = "1.0.0", app: str = "1.0.0"
) -> tuple[LayerVersions, ...]:
    return (
        layer("core", "1.0.0", commit=core),
        layer("service", "1.0.0", commit=service, ancestors=["core"]),
        layer("app", "1.0.0", commit=app, ancestors=["core", "service"]),
    )


def _wanted(**overrides: str) -> dict[str, SerializableVersion]:
    return {k: v(t) for k, t in {**TARGETS, **overrides}.items()}


class TestAFreshUpdate:
    """With nothing pending, every layer runs to the planned targets."""

    def test_every_layer_runs_with_its_old_copy(self) -> None:
        resolution = resolve_versions(_layers(), _wanted(), None)

        assert resolution.resume is None
        assert tuple(resolution.old_copies) == ("core", "service", "app")
        assert dict(resolution.targets) == _wanted()
        assert resolution.warnings == ()

    def test_a_hand_run_of_one_layer_warns_and_proceeds(self) -> None:
        resolution = resolve_versions(
            _layers(service="1.1.0"), _wanted(service="1.2.0"), None
        )

        assert [w.layer for w in resolution.warnings] == ["service"]
        assert resolution.old_copies["service"].commit == "1.1.0"

    def test_a_hand_run_of_a_layer_and_an_ancestor_stops(self) -> None:
        with pytest.raises(UpdateLayerDriftError):
            resolve_versions(_layers(core="1.1.0", service="1.1.0"), _wanted(), None)

    def test_a_downgrade_stops(self) -> None:
        with pytest.raises(UpdateDowngradeError):
            resolve_versions(_layers(app="1.1.0"), _wanted(app="1.0.0"), None)


class TestAGivenResumePlan:
    """The plan the caller already made decides the walk; none is made again."""

    @staticmethod
    def _plan() -> ResumePlan:
        return ResumePlan(
            finished=("core", "service"), remaining=("app",), targets=_wanted()
        )

    def test_runs_only_the_layers_the_plan_leaves(self) -> None:
        """Pass no record: only the given plan can say that core finished."""
        resolution = resolve_versions(
            _layers(core="2.0.0"), _wanted(core="3.0.0"), self._plan()
        )

        assert resolution.resume == self._plan()
        assert tuple(resolution.old_copies) == ("app",)

    def test_takes_the_plans_targets_over_the_planned_ones(self) -> None:
        resolution = resolve_versions(
            _layers(core="2.0.0"), _wanted(core="3.0.0"), self._plan()
        )

        assert dict(resolution.targets) == _wanted()

    def test_a_remaining_layers_old_copy_uses_the_locks_ancestor_versions(
        self,
    ) -> None:
        resolution = resolve_versions(_layers(core="2.0.0"), _wanted(), self._plan())

        assert dict(resolution.old_copies["app"].versions) == {
            "core": v("1.0.0"),
            "service": v("1.0.0"),
            "app": v("1.0.0"),
        }

    def test_the_drift_rule_does_not_apply_to_a_resume(self) -> None:
        """Core and service both moved in the paused walk; the plan owns that."""
        layers = _layers(core="2.0.0", service="1.1.0")

        resolution = resolve_versions(layers, _wanted(service="1.1.0"), self._plan())

        assert resolution.warnings == ()
