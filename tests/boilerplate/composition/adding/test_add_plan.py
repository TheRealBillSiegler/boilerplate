"""``AddPlan.unsafe_for`` decides the ``unsafe`` grant of the add's copy.

The expected values are Copier's own ``Worker._check_unsafe`` for a copy: it
counts the layer's tasks only when the copy does not skip them.
"""

from datetime import UTC, datetime

import pytest

from boilerplate.composition.adding.add_plan import AddPlan
from boilerplate.composition.updating.layer_release import LayerRelease
from boilerplate.composition.views import LayerView
from boilerplate.models import BoilerplateLock, LockLayer
from boilerplate.types import SerializableVersion

STAMP = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)


def _plan(*, needs_unsafe: bool, tasks: tuple[str, ...]) -> AddPlan:
    """Return a plan for the layer ``docs`` with the given grant inputs."""
    return AddPlan(
        lock=BoilerplateLock(
            boilerplate_version="0.3.0",
            copier_version="9.18.1",
            created_at=STAMP,
            updated_at=STAMP,
            root_template="core@1.0.0",
            layers=(
                LockLayer(
                    name="core",
                    version=SerializableVersion("1.0.0"),
                    source="x",
                    checksum="sha256:" + "a" * 64,
                ),
            ),
        ),
        release=LayerRelease(layer="docs", source="x", ref="1.0.0"),
        version="1.0.0",
        view=LayerView({}, ()),
        tasks=tasks,
        needs_unsafe=needs_unsafe,
    )


class TestUnsafeFor:
    @pytest.mark.parametrize("skip_tasks", [True, False])
    def test_a_layer_that_loads_an_extension_is_granted(self, skip_tasks: bool) -> None:
        plan = _plan(needs_unsafe=True, tasks=())

        assert plan.unsafe_for(skip_tasks=skip_tasks) is True

    @pytest.mark.parametrize(("skip_tasks", "expected"), [(True, False), (False, True)])
    def test_a_task_is_granted_only_when_the_copy_runs_it(
        self, skip_tasks: bool, expected: bool
    ) -> None:
        plan = _plan(needs_unsafe=False, tasks=("echo hi",))

        assert plan.unsafe_for(skip_tasks=skip_tasks) is expected

    @pytest.mark.parametrize("skip_tasks", [True, False])
    def test_a_layer_that_declares_nothing_keeps_copiers_consent_gate(
        self, skip_tasks: bool
    ) -> None:
        plan = _plan(needs_unsafe=False, tasks=())

        assert plan.unsafe_for(skip_tasks=skip_tasks) is False
