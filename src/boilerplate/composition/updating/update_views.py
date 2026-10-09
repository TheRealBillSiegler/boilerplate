"""The two views an update of one layer renders under, and the grant they need."""

from typing import NamedTuple

from boilerplate.composition.views import LayerView


class UpdateViews(NamedTuple):
    """The views of the layer and its ancestors before and after an update.

    The two differ when an ancestor moves, even if the layer's own ref stays
    put, so a view keyed by the layer's ref cannot hold both.

    The grant is part of the pair because the same releases decide it. Copier's
    own check (``Worker._check_unsafe``) reads the extensions of both releases,
    the tasks of the recorded one and the migrations of the target one, and the
    target's tasks only when the step runs them. The grant covers those and no
    more: ``unsafe`` also switches off Copier's check that a render stays inside
    the project.

    Attributes:
        old: The view at the recorded releases, for the old copy.
        target: The view at the target releases, for the in-place render and
            the new copy.
        needs_unsafe: Whether the step needs Copier's ``unsafe`` grant whether
            or not it runs the target release's tasks.
        tasks_need_unsafe: Whether the target release declares tasks, which
            Copier counts only when the step runs them.
    """

    old: LayerView
    target: LayerView
    needs_unsafe: bool
    tasks_need_unsafe: bool = False

    def unsafe_for(self, *, skip_tasks: bool) -> bool:
        """Return whether the step is granted ``unsafe``, given whether it skips tasks.

        Args:
            skip_tasks: Whether the step skips the layer's own tasks.

        Returns:
            True when Copier's check flags a feature of the step.
        """
        return self.needs_unsafe or (self.tasks_need_unsafe and not skip_tasks)
