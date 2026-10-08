"""Everything an update decides before it touches the checkout."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from boilerplate.composition.updating.layer_release import LayerRelease
from boilerplate.composition.updating.walk.walk_step import WalkStep
from boilerplate.composition.views import LayerView
from boilerplate.models import BoilerplateLock
from boilerplate.types.serializable_version import SerializableVersion


@dataclass(frozen=True)
class WalkPlan:
    """The outcome of the pre-walk checks: what to run and what to warn of.

    Attributes:
        lock: The lock the update starts from.
        layers: Every layer of the project in the lock's order, root last.
        steps: The layers the walk runs, in walk order.
        skipped: The layers a resumed walk skips because the paused walk
            finished them, in walk order.
        targets: The version every layer moves to.
        root_release: The root layer's release, for the post-walk task run.
        task_view: The root layer's view at the target releases.
        tasks: The composition's accumulated tasks at the target releases.
        warnings: Findings that do not stop the update.
    """

    lock: BoilerplateLock
    layers: tuple[str, ...]
    steps: tuple[WalkStep, ...]
    skipped: tuple[str, ...]
    targets: Mapping[str, SerializableVersion]
    root_release: LayerRelease
    task_view: LayerView
    tasks: tuple[Any, ...]
    warnings: tuple[str, ...]

    @property
    def root(self) -> str:
        """The composition's final layer."""
        return self.layers[-1]
