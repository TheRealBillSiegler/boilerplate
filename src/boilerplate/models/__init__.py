"""Template data models and metadata for Boilerplate."""

from boilerplate.models.boilerplate_lock import (
    LOCK_SCHEMA_MAJOR,
    LOCK_SCHEMA_VERSION,
    BoilerplateLock,
)
from boilerplate.models.change_classification import ChangeClassification
from boilerplate.models.joined_via import JoinedVia
from boilerplate.models.lock_layer import LockLayer
from boilerplate.models.migration_record import MigrationRecord
from boilerplate.models.migration_status import MigrationStatus
from boilerplate.models.restore_kind import RestoreKind
from boilerplate.models.restore_marker import RestoreMarker
from boilerplate.models.restore_operation import RestoreOperation
from boilerplate.models.restore_phase import RestorePhase
from boilerplate.models.template_info import TemplateInfo
from boilerplate.models.template_meta import SCHEMA_VERSION, TemplateMeta

__all__ = [
    "LOCK_SCHEMA_MAJOR",
    "LOCK_SCHEMA_VERSION",
    "SCHEMA_VERSION",
    "BoilerplateLock",
    "ChangeClassification",
    "JoinedVia",
    "LockLayer",
    "MigrationRecord",
    "MigrationStatus",
    "RestoreKind",
    "RestoreMarker",
    "RestoreOperation",
    "RestorePhase",
    "TemplateInfo",
    "TemplateMeta",
]
