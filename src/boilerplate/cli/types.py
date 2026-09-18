"""CLI data types and enums."""

from enum import StrEnum


class DataFormat(StrEnum):
    """Supported output formats for data sections."""

    YAML = "yaml"
    JSON = "json"


class TextFormat(StrEnum):
    """Output formats for commands whose human-readable output is plain text."""

    TEXT = "text"
    JSON = "json"


class Section(StrEnum):
    """All selectable compose sections."""

    FINAL = "final"
    LAYERS = "layers"
    STATES = "states"
    DELTAS = "deltas"
    STATS = "stats"
