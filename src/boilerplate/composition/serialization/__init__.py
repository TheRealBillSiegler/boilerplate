"""Serialization helpers for JSON and YAML outputs.

This package provides thin, well-typed wrappers for dumping composition
artifacts to JSON and YAML, plus helpers for converting data into a
YAML-friendly form and extracting copier configuration.

- dump_json(...), write_json(...): Serialize/emit JSON.
- dump_yaml(...), write_yaml(...): Serialize/emit YAML.
- serialize_for_yaml(...): Convert data to YAML-safe structures.
- extract_complete_copier_config(...): Build a final copier config mapping.

Canonical import:
    >>> from boilerplate.composition.serialization import dump_yaml  # doctest: +SKIP

Examples:
    >>> dump_yaml({"name": "example"})  # doctest: +ELLIPSIS
    'name: example...'
"""

from boilerplate.composition.serialization.composition_writer_json import (
    dump_json,
    write_json,
)
from boilerplate.composition.serialization.composition_writer_yaml import (
    dump_yaml,
    write_yaml,
)
from boilerplate.composition.serialization.yaml_utils import (
    extract_complete_copier_config,
    serialize_for_yaml,
)

__all__ = [
    "dump_json",
    "dump_yaml",
    "extract_complete_copier_config",
    "serialize_for_yaml",
    "write_json",
    "write_yaml",
]
