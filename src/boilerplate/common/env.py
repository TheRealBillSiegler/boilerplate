"""Environment-variable helpers shared across layers."""

import os

_ENV_FLAG_FALSY = {"0", "false"}


def env_flag(name: str) -> bool:
    """Returns whether env var ``name`` opts into a boolean mode flag.

    Surrounding whitespace is trimmed before the check, so a whitespace-only
    value reads as unset. Truthy for any remaining value except unset,
    empty, ``0``, or ``false`` (case-insensitive) — mirroring the
    ``CI=false`` escape hatch from ci-info, applied per tool-scoped opt-in
    variable rather than the generic ``CI``.
    """
    value = os.environ.get(name, "").strip()
    return bool(value) and value.lower() not in _ENV_FLAG_FALSY
