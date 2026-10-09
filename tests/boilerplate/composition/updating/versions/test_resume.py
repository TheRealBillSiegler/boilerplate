"""Tests for planning the resume of a paused update in resume.py."""

import pytest

from boilerplate.common.exceptions import UpdateTargetMismatchError
from boilerplate.composition.updating.versions import LayerVersions, plan_resume
from tests.boilerplate.composition.updating.versions.conftest import (
    conflict,
    layer,
    success,
    v,
)

TARGETS = {"core": "2.0.0", "service": "1.0.0", "app": "1.1.0"}


def _layers(*, core: str = "2.0.0", service: str = "1.0.0", app: str = "1.0.0"):
    """Return three layers as a walk paused after `service` leaves them."""
    return (
        layer("core", "1.0.0", commit=core),
        layer("service", "1.0.0", commit=service, ancestors=["core"]),
        layer("app", "1.0.0", commit=app, ancestors=["core", "service"]),
    )


class TestAPausedWalkResumes:
    """A conflict record whose finished layers record its targets binds."""

    def test_skips_the_finished_layers_and_keeps_the_recorded_targets(self) -> None:
        plan = plan_resume(_layers(), conflict(TARGETS, ["core", "service"]))

        assert plan is not None
        assert plan.finished == ("core", "service")
        assert plan.remaining == ("app",)
        assert dict(plan.targets) == {k: v(t) for k, t in TARGETS.items()}

    def test_skips_a_finished_layer_whose_own_version_did_not_move(self) -> None:
        """Service ran in the paused walk but stays at 1.0.0; the record knows."""
        plan = plan_resume(_layers(), conflict(TARGETS, ["core", "service"]))

        assert plan is not None
        assert "service" in plan.finished
        assert "service" not in plan.remaining

    def test_remaining_layers_keep_the_locks_walk_order(self) -> None:
        plan = plan_resume(_layers(), conflict(TARGETS, ["core"]))

        assert plan is not None
        assert plan.remaining == ("service", "app")

    def test_targets_keep_the_locks_walk_order(self) -> None:
        """Order the targets as the walk runs, root last, not as the record keeps them.

        The migrations file is written with sorted keys, so a record's targets
        read back alphabetically; the restore marker takes its walk-ordered
        targets from this plan (design 02 §RestoreMarker).
        """
        alphabetical = dict(sorted(TARGETS.items()))

        plan = plan_resume(_layers(), conflict(alphabetical, ["core"]))

        assert plan is not None
        assert list(plan.targets) == ["core", "service", "app"]

    def test_an_explicit_target_equal_to_the_recorded_one_is_accepted(self) -> None:
        plan = plan_resume(
            _layers(), conflict(TARGETS, ["core", "service"]), {"app": v("1.1.0")}
        )

        assert plan is not None


class TestARecordThatDoesNotBind:
    """Without a binding conflict record, the update plans afresh."""

    def test_no_record_means_no_resume(self) -> None:
        assert plan_resume(_layers(), None) is None

    def test_a_record_that_is_not_a_conflict_means_no_resume(self) -> None:
        assert plan_resume(_layers(), success()) is None

    def test_a_finished_layer_that_no_longer_records_its_target_means_no_resume(
        self,
    ) -> None:
        """The partial update was set aside: core is back at 1.0.0."""
        layers = _layers(core="1.0.0")

        assert plan_resume(layers, conflict(TARGETS, ["core", "service"])) is None

    def test_a_finished_layer_retargeted_by_hand_means_no_resume(self) -> None:
        layers = _layers(core="2.1.0")

        assert plan_resume(layers, conflict(TARGETS, ["core", "service"])) is None

    def test_a_finished_layer_whose_commit_yields_no_version_means_no_resume(
        self,
    ) -> None:
        stray: LayerVersions = _layers()[0].model_copy(update={"commit_version": None})
        layers = (stray, *_layers()[1:])

        assert plan_resume(layers, conflict(TARGETS, ["core"])) is None

    def test_a_record_for_other_layers_means_no_resume(self) -> None:
        other = conflict({"core": "2.0.0", "ghost": "1.0.0"}, ["core"])

        assert plan_resume(_layers(), other) is None


class TestAnExplicitTargetThatDiffers:
    """An explicit target that differs from the recorded one stops the update."""

    @pytest.mark.parametrize(
        ("layer_name", "requested"), [("app", "1.2.0"), ("core", "3.0.0")]
    )
    def test_is_refused(self, layer_name: str, requested: str) -> None:
        with pytest.raises(UpdateTargetMismatchError) as caught:
            plan_resume(
                _layers(),
                conflict(TARGETS, ["core", "service"]),
                {layer_name: v(requested)},
            )

        assert caught.value.layers == (layer_name,)
        assert requested in str(caught.value)
        assert TARGETS[layer_name] in str(caught.value)

    def test_is_not_refused_when_the_record_does_not_bind(self) -> None:
        """After the partial update is set aside, the user may retarget."""
        layers = _layers(core="1.0.0")

        assert (
            plan_resume(
                layers, conflict(TARGETS, ["core", "service"]), {"app": v("1.2.0")}
            )
            is None
        )
