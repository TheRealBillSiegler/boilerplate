"""Local CI gate: run the same checks the CI workflow runs, before pushing.

A failure caught here costs seconds; the same failure in CI costs a full
billed run plus the rerun after the fix. Mirrors the lint, typecheck, test,
scenarios, and docs jobs in ``.github/workflows/ci.yml``, and the
commit-message lint in ``.github/workflows/pr-checks.yml`` (the package smoke
test, ShellCheck, and the new-tests-go-red check are CI-only). The composition
scenarios run only when a composition path differs from the merge base with
``origin/develop``, the way CI runs them only when its diff touches one; the
gate prints which choice it made and why. Contributor instructions:
``docs/governance/ci.md``.

Usage:
    uv run python scripts/check.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Final

_REPO_ROOT: Final = Path(__file__).resolve().parent.parent

# The paths whose change turns the scenarios on. All of ``src/boilerplate/``
# counts: the scenarios drive the CLI, which reaches every package under it.
# Keep in step with the ``composition`` output of the ``changes`` job in
# ``.github/workflows/ci.yml``.
_COMPOSITION_DIRS: Final = (
    "src/boilerplate/",
    "tests/integration/boilerplate/composition/",
    "tests/boilerplate/templates/",
    "tests/fixtures/family/",
)
_COMPOSITION_FILES: Final = ("uv.lock", ".github/workflows/ci.yml")
_BASE_BRANCH: Final = "origin/develop"
_SCENARIOS: Final = ["uv", "run", "pytest", "-m", "scenario"]

# (argv, extra environment) per gate step, in fail-fast order: cheap static
# checks first, the test suite, the doctests and both strict docs configs, and
# the scenarios last when ``main`` decides they run, so a failure in a cheap
# step never waits behind a scenario run.
_STEPS: Final[list[tuple[list[str], dict[str, str]]]] = [
    (["uv", "run", "ruff", "check", "--no-fix", "."], {}),
    (["uv", "run", "ruff", "format", "--check", "."], {}),
    (["uv", "run", "python", "scripts/commit_lint.py"], {}),
    (["uv", "run", "pyright"], {}),
    (["uv", "run", "pytest", "-m", "not scenario"], {}),
    (["uv", "run", "pytest", "--doctest-modules", "src", "-n0"], {}),
    (["uv", "run", "mkdocs", "build", "--strict"], {}),
    (
        ["uv", "run", "mkdocs", "build", "--strict", "--site-dir", "site-offline"],
        {"DOCS_OFFLINE": "true"},
    ),
    (_SCENARIOS, {}),
]


def touches_composition(paths: Iterable[str]) -> bool:
    """Return whether any of `paths` is one the scenarios run for.

    Args:
        paths: Repository-relative paths with forward slashes.

    Returns:
        True when a path is under a composition directory or is a listed file.
    """
    return any(
        path.startswith(_COMPOSITION_DIRS) or path in _COMPOSITION_FILES
        for path in paths
    )


def scenario_choice(
    merge_base: str | None, changed: Sequence[str] | None
) -> tuple[bool, str]:
    """Decide whether the gate runs the scenarios, and say why.

    Args:
        merge_base: The merge base with ``origin/develop``, or None when git
            could not find one.
        changed: The paths that differ from the merge base, or None when git
            could not list them.

    Returns:
        Whether to run the scenarios, and the reason to print.
    """
    if merge_base is None:
        return True, f"running them, no merge base with {_BASE_BRANCH}"
    if changed is None:
        return True, f"running them, could not diff against {merge_base[:7]}"
    hits = [path for path in changed if touches_composition([path])]
    if not hits:
        return False, f"skipped, no composition path differs from {_BASE_BRANCH}"
    more = f" and {len(hits) - 1} more" if len(hits) > 1 else ""
    return True, f"running them, {hits[0]}{more} differs from {_BASE_BRANCH}"


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    """Run git in the repository root, capturing its output."""
    return subprocess.run(
        ["git", *args],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def _scenarios_wanted() -> bool:
    """Print and return whether this checkout's changes call for the scenarios."""
    base = _git("merge-base", "HEAD", _BASE_BRANCH)
    merge_base = base.stdout.strip() if base.returncode == 0 else ""
    changed: list[str] | None = None
    if merge_base:
        # The working tree against the merge base, renames listed as the
        # deletion and the addition, plus files git does not track yet.
        diff = _git("diff", "--name-only", "--no-renames", merge_base)
        untracked = _git("ls-files", "--others", "--exclude-standard")
        if diff.returncode == 0 and untracked.returncode == 0:
            changed = [*diff.stdout.splitlines(), *untracked.stdout.splitlines()]
    run, reason = scenario_choice(merge_base or None, changed)
    print(f"\n=== scenarios: {reason}", flush=True)
    return run


def main() -> int:
    """Run every gate step, stopping at the first failure.

    Returns:
        Process exit code: 0 when every step passes, 1 otherwise.
    """
    for argv, extra_env in _STEPS:
        if argv is _SCENARIOS and not _scenarios_wanted():
            continue
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
