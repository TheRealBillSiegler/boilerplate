"""The versions an update walk runs at."""
# Spec: docs/design/04-composition-engine.md §Safe Update

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict

from boilerplate.composition.updating.versions.drift_warning import DriftWarning
from boilerplate.composition.updating.versions.old_copy import OldCopy
from boilerplate.composition.updating.versions.resume_plan import ResumePlan
from boilerplate.types.serializable_version import SerializableVersion

__all__ = ["VersionResolution"]


class VersionResolution(BaseModel):
    """What the pre-walk checks decided about the versions of an update.

    Attributes:
        targets: The version every layer moves to: the recorded targets of a
            resumed update, otherwise the planned ones.
        resume: The plan that resumes a paused update, or ``None`` for a fresh
            one.
        warnings: Layers that disagree with the lock without stopping the
            update; empty on a resume.
        old_copies: The old-copy versions of each layer the walk runs, keyed by
            name and in walk order; a resumed update's finished layers are not
            among them.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    targets: Mapping[str, SerializableVersion]
    resume: ResumePlan | None
    warnings: tuple[DriftWarning, ...]
    old_copies: Mapping[str, OldCopy]
