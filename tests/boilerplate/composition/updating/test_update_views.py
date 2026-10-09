"""``UpdateViews.unsafe_for`` decides the ``unsafe`` grant of one update step.

The expected values are Copier's own ``Worker._check_unsafe``: it counts the
tasks of the target release only when the step does not skip them.
"""

import pytest

from boilerplate.composition.updating.update_views import UpdateViews
from boilerplate.composition.views import LayerView

VIEW = LayerView({}, ())


class TestUnsafeFor:
    @pytest.mark.parametrize("skip_tasks", [True, False])
    def test_a_step_with_a_feature_copier_always_counts_is_granted(
        self, skip_tasks: bool
    ) -> None:
        """Grant an extension, a recorded task or a migration, tasks run or not."""
        views = UpdateViews(VIEW, VIEW, needs_unsafe=True)

        assert views.unsafe_for(skip_tasks=skip_tasks) is True

    @pytest.mark.parametrize(("skip_tasks", "expected"), [(True, False), (False, True)])
    def test_a_target_task_is_granted_only_when_the_step_runs_it(
        self, skip_tasks: bool, expected: bool
    ) -> None:
        views = UpdateViews(VIEW, VIEW, needs_unsafe=False, tasks_need_unsafe=True)

        assert views.unsafe_for(skip_tasks=skip_tasks) is expected

    @pytest.mark.parametrize("skip_tasks", [True, False])
    def test_a_step_with_nothing_to_grant_keeps_copiers_consent_gate(
        self, skip_tasks: bool
    ) -> None:
        views = UpdateViews(VIEW, VIEW, needs_unsafe=False)

        assert views.unsafe_for(skip_tasks=skip_tasks) is False
