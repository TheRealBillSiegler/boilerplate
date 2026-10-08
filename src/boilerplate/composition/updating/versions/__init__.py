"""Pre-walk version rules: old copies, resume, drift and downgrades.

Every rule here is a pure function over parsed versions. Reading a layer's
``_commit`` as a version needs its template repository, so it happens in
``read_layer_versions`` before these run.
"""

from boilerplate.composition.updating.versions.downgrades import reject_downgrades
from boilerplate.composition.updating.versions.drift import check_drift
from boilerplate.composition.updating.versions.drift_warning import DriftWarning
from boilerplate.composition.updating.versions.layer_versions import LayerVersions
from boilerplate.composition.updating.versions.layer_versions_reader import (
    read_layer_versions,
)
from boilerplate.composition.updating.versions.old_copies import old_copy_for
from boilerplate.composition.updating.versions.old_copy import OldCopy
from boilerplate.composition.updating.versions.resolve_versions import resolve_versions
from boilerplate.composition.updating.versions.resume import plan_resume
from boilerplate.composition.updating.versions.resume_plan import ResumePlan
from boilerplate.composition.updating.versions.version_resolution import (
    VersionResolution,
)

__all__ = [
    "DriftWarning",
    "LayerVersions",
    "OldCopy",
    "ResumePlan",
    "VersionResolution",
    "check_drift",
    "old_copy_for",
    "plan_resume",
    "read_layer_versions",
    "reject_downgrades",
    "resolve_versions",
]
