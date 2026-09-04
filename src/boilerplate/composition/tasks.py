"""Single owner of ``_tasks`` semantics across composition and rendering.

The ``_tasks`` key accumulates across layers (strategy registered in
``CopierConfigMerger``), is excluded from per-layer directive values, is
preserved in Copier's native task shapes, and currently executes once on
the final layer of a render (see design/adr-014-deferred-task-execution.md).

Copier assigns different execution semantics per shape — a plain string runs
under the system shell, an argv list runs without a shell, and a mapping
(``command`` plus optional ``when``/``working_directory``) adds a condition
or working directory — so these helpers pass shapes through rather than
re-encode them, leaving interpretation to Copier.
"""

from __future__ import annotations

from collections.abc import Iterable
from logging import getLogger
from typing import TYPE_CHECKING, Final

# Runtime project imports are forbidden here: merger.py imports this module
# while the composition package is still initializing, and any import that
# reaches models/__init__ re-enters this module via serialization/yaml_utils
# before TASKS_KEY is bound. This module must stay a leaf.
if TYPE_CHECKING:
    from boilerplate.composition.models.json_types import JSON

TASKS_KEY: Final = "_tasks"

_logger = getLogger(__name__)

_DEFAULT_CONDITIONS: Final = ("true", "", None, True)


def coerce_task(item: object) -> JSON:
    """Projects a Copier Task-like object back to its raw ``copier.yml`` shape.

    Execution semantics survive the round trip: a string command stays a
    shell string, an argv command stays a list, and a non-default
    ``condition`` or ``working_directory`` is carried in Copier's mapping
    form (``command``/``when``/``working_directory``).

    Args:
        item: Object exposing a ``cmd`` attribute (e.g. a Copier
            Task), optionally with ``condition`` and ``working_directory``.

    Returns:
        The raw task shape — string, list of strings, or mapping —
        or ``str(item)`` when no usable ``cmd`` is present.

    Example:
        A guarded task keeps its condition; an unguarded argv passes bare:

        >>> class Guarded:
        ...     cmd = "rm -rf build"
        ...     condition = "{{ cleanup }}"
        >>> coerce_task(Guarded())
        {'command': 'rm -rf build', 'when': '{{ cleanup }}'}
        >>> class Plain:
        ...     cmd = ("git", "init")
        >>> coerce_task(Plain())
        ['git', 'init']
    """
    cmd = getattr(item, "cmd", None)
    command: JSON
    if isinstance(cmd, str):
        command = cmd
    elif isinstance(cmd, Iterable):
        command = [str(x) for x in cmd]
    else:
        return str(item)

    extras: dict[str, JSON] = {}
    condition = getattr(item, "condition", None)
    if isinstance(condition, str | bool) and condition not in _DEFAULT_CONDITIONS:
        extras["when"] = condition
    working_directory = str(getattr(item, "working_directory", "."))
    if working_directory not in (".", ""):
        extras["working_directory"] = working_directory

    if extras:
        return {"command": command, **extras}
    return command


def normalize_tasks(final_schema: dict[str, JSON]) -> list[JSON]:
    """Extracts tasks from the merged final schema in Copier's native shapes.

    Strings, argv lists, and ``command`` mappings pass through unchanged so
    Copier — not Boilerplate — interprets their execution semantics; list
    elements are stringified for serialization safety. Anything else is
    dropped with a warning.

    Args:
        final_schema: The merged final schema from
            ``Composition.final``.

    Returns:
        Task entries in Copier's native shapes; ``[]`` when no
        valid tasks exist.

    Example:
        Strings keep shell semantics; mappings keep their condition:

        >>> normalize_tasks({"_tasks": ["echo hi", ["git", "init"]]})
        ['echo hi', ['git', 'init']]
        >>> normalize_tasks({"_tasks": [{"command": "x", "when": "{{ y }}"}]})
        [{'command': 'x', 'when': '{{ y }}'}]
    """
    maybe_tasks = final_schema.get(TASKS_KEY)
    if not isinstance(maybe_tasks, list):
        return []
    tasks: list[JSON] = []
    for entry in maybe_tasks:
        if isinstance(entry, str):
            tasks.append(entry)
        elif isinstance(entry, list):
            tasks.append([str(x) for x in entry])
        elif isinstance(entry, dict) and "command" in entry:
            tasks.append(entry)
        else:
            _logger.warning("Dropping malformed _tasks entry: %r", entry)
    return tasks


__all__ = ["TASKS_KEY", "coerce_task", "normalize_tasks"]
