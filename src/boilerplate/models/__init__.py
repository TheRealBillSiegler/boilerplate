"""Template data models and metadata for Boilerplate."""

from boilerplate.models.boilerplate_lock import LOCK_SCHEMA_VERSION, BoilerplateLock
from boilerplate.models.lock_layer import LockLayer
from boilerplate.models.template_info import TemplateInfo
from boilerplate.models.template_meta import SCHEMA_VERSION, TemplateMeta

__all__ = [
    "LOCK_SCHEMA_VERSION",
    "SCHEMA_VERSION",
    "BoilerplateLock",
    "LockLayer",
    "TemplateInfo",
    "TemplateMeta",
]
