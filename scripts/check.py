"""Local CI gate: run the same checks the CI workflow runs, before pushing.

A failure caught here costs seconds; the same failure in CI costs a full
billed run plus the rerun after the fix. Mirrors the lint, typecheck, test,
and docs jobs in ``.github/workflows/ci.yml`` (the package smoke test and
ShellCheck are CI-only).

Usage:
    uv run python scripts/check.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Final

_REPO_ROOT: Final = Path(__file__).resolve().parent.parent

# (argv, extra environment) per gate step, in fail-fast order: cheap static
# checks first, the test suite, then both strict docs configs.
_STEPS: Final[list[tuple[list[str], dict[str, str]]]] = [
    (["uv", "run", "ruff", "check", "--no-fix", "."], {}),
    (["uv", "run", "ruff", "format", "--check", "."], {}),
    (["uv", "run", "pyright"], {}),
    (["uv", "run", "pytest"], {}),
    (["uv", "run", "pytest", "--doctest-modules", "src", "-n0"], {}),
    (["uv", "run", "mkdocs", "build", "--strict"], {}),
    (
        ["uv", "run", "mkdocs", "build", "--strict", "--site-dir", "site-offline"],
        {"DOCS_OFFLINE": "true"},
    ),
]


def main() -> int:
    """Run every gate step, stopping at the first failure.

    Returns:
        Process exit code: 0 when every step passes, 1 otherwise.
    """
    for argv, extra_env in _STEPS:
        print(f"\n=== {' '.join(argv)}", flush=True)
        result = subprocess.run(
            argv,
            cwd=_REPO_ROOT,
            env={**os.environ, **extra_env},
            check=False,
        )
        if result.returncode != 0:
            print(f"\nGATE FAILED at: {' '.join(argv)}", file=sys.stderr)
            return 1
    for site_dir in ("site", "site-offline"):
        shutil.rmtree(_REPO_ROOT / site_dir, ignore_errors=True)
    print("\nAll gate steps passed; safe to push.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
