"""Everything an add decides before it touches the checkout."""

from dataclasses import dataclass

from boilerplate.composition.models.json_types import JSON
from boilerplate.composition.updating.layer_release import LayerRelease
from boilerplate.composition.views import LayerView
from boilerplate.models import BoilerplateLock


@dataclass(frozen=True)
class AddPlan:
    """The outcome of the pre-staging checks: what to render and what follows.

    Attributes:
        lock: The lock the add starts from.
        release: The layer to add and the release to add it at.
        version: The version of that release.
        view: The layer's view against the project's layers at their locked
            releases and the layer at its release.
        tasks: The layer's own tasks.
        needs_unsafe: Whether the add's copy needs Copier's ``unsafe`` grant
            whether or not it runs the layer's tasks: the view loads an
            extension, or the layer declares one. Copier counts no migration
            of a copy.
    """

    lock: BoilerplateLock
    release: LayerRelease
    version: str
    view: LayerView
    tasks: tuple[JSON, ...]
    needs_unsafe: bool

    def unsafe_for(self, *, skip_tasks: bool) -> bool:
        """Return whether a copy that skips tasks, or not, is granted ``unsafe``.

        Copier's own check counts a copy's tasks only when it runs them, so the
        grant follows the extensions alone for the copy that skips them.

        Args:
            skip_tasks: Whether the copy skips the layer's own tasks.

        Returns:
            True when Copier's check flags a feature of the copy.
        """
        return self.needs_unsafe or (bool(self.tasks) and not skip_tasks)

    @property
    def layer(self) -> str:
        """The name of the layer being added."""
        return self.release.layer

    @property
    def layers(self) -> tuple[str, ...]:
        """Every layer of the project after the add, the new layer last."""
        return (*(entry.name for entry in self.lock.layers), self.layer)
