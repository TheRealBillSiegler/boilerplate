"""Enforces the mutation-score ratchet: a package's score may rise, never fall.

Compares each package's mutation score (killed / total, from ``mutmut results
--all``) against the stored baseline in ``tests/mutation-baseline.json``; a fall of
more than ``tolerance`` fails the check. What this scores, when it runs, and how to
raise the baseline are documented in ``docs/governance/contributing.md``.

The baseline is first established with an empty JSON object (``{}``): every package is
then "new" (see ``compare``), the check passes, and the workflow's first real run
produces the scores a maintainer commits as the starting baseline.

Status bucketing (mutmut's ``status_by_exit_code``, from ``mutmut/stats.py``): a mutant
counts toward ``total`` unless mutmut marks it ``skipped`` (an explicit ``# pragma: no
mutate``) or ``not checked`` (never run at all); it counts toward ``killed`` only when
its status is exactly ``killed``. Every other final status — ``survived``, ``timeout``,
``suspicious``, ``no tests``, ``caught by type check``, ``segfault``, ``check was
interrupted by user`` — counts toward ``total`` but not ``killed``: each represents a
mutant that ran (or mutmut decided about) without a test proving it wrong.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path

_KILLED_STATUSES = frozenset({"killed"})
_EXCLUDED_STATUSES = frozenset({"skipped", "not checked"})
# A mutant key is "boilerplate.<package>.<...>", so splitting on "." needs at least
# this many segments to name a package.
_MIN_KEY_SEGMENTS = 2


def parse_results(text: str) -> dict[str, tuple[int, int]]:
    """Parse ``mutmut results --all`` output into per-package (killed, total) pairs.

    Each non-blank line has the form ``    <key>: <status>``, where ``key`` is a
    mutant's dotted module path plus mangled function name (e.g.
    ``boilerplate.common.env.x_get_env_var__mutmut_1``), always rooted at
    ``boilerplate`` because mutmut strips the ``src.`` prefix. The top-level package
    is the second dotted component.

    Args:
        text: The full stdout of ``mutmut results --all``.

    Returns:
        A mapping from top-level package name (e.g. ``"composition"``) to a
        ``(killed, total)`` pair. ``total`` counts every mutant whose status is not
        ``"skipped"`` or ``"not checked"``; ``killed`` counts the subset of those
        with status exactly ``"killed"``.

    Raises:
        ValueError: If a non-blank line does not match the ``<key>: <status>``
            format, or a key's module path does not start with ``boilerplate.``.

    Example:
        >>> parse_results("    boilerplate.common.env.x_f__mutmut_1: killed")
        {'common': (1, 1)}
    """
    counts: dict[str, tuple[int, int]] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        key, sep, status = stripped.partition(": ")
        if not sep:
            raise ValueError(f"Line does not match '<key>: <status>' format: {line!r}")
        parts = key.split(".")
        if len(parts) < _MIN_KEY_SEGMENTS or parts[0] != "boilerplate":
            raise ValueError(
                f"Mutant key does not start with 'boilerplate.<package>.': {key!r}"
            )
        if status in _EXCLUDED_STATUSES:
            continue
        package = parts[1]
        killed, total = counts.get(package, (0, 0))
        total += 1
        if status in _KILLED_STATUSES:
            killed += 1
        counts[package] = (killed, total)
    return counts


def scores(per_package: Mapping[str, tuple[int, int]]) -> dict[str, float]:
    """Compute killed/total mutation scores, omitting packages with no mutants.

    Args:
        per_package: Mapping from package name to a ``(killed, total)`` pair, as
            returned by ``parse_results``.

    Returns:
        Mapping from package name to its mutation score, rounded to 4 decimal
        places. A package whose ``total`` is 0 is omitted rather than reported as a
        (misleading) 0.0 or division-by-zero.

    Example:
        >>> scores({"common": (3, 4), "empty": (0, 0)})
        {'common': 0.75}
    """
    result: dict[str, float] = {}
    for package, (killed, total) in per_package.items():
        if total == 0:
            continue
        result[package] = round(killed / total, 4)
    return result


def compare(
    current: Mapping[str, float],
    baseline: Mapping[str, float],
    tolerance: float = 0.0,
) -> tuple[int, str]:
    """Check current mutation scores against a baseline, enforcing the ratchet.

    A package present in both ``current`` and ``baseline`` fails the check when its
    score dropped by more than ``tolerance``. A package present only in ``current``
    is reported as new to the baseline and never fails the check on its own. A
    package present only in ``baseline`` (e.g. removed or renamed) is reported but,
    like a new package, never fails the check on its own — only a drop does.

    Args:
        current: This run's scores, as returned by ``scores``.
        baseline: The stored baseline scores to compare against.
        tolerance: The maximum score drop, in the same 0-1 units as the scores, that
            does not count as a regression. Defaults to 0.0 (any drop fails).

    Returns:
        A ``(exit_code, message)`` pair: ``exit_code`` is 1 if any shared package
        dropped by more than ``tolerance``, else 0. ``message`` lists every package
        present in both with its baseline, current, and delta, followed by any
        packages new to the baseline or missing from the current run.

    Example:
        >>> code, message = compare({"common": 0.9}, {"common": 0.95})
        >>> code
        1
        >>> "common" in message
        True
    """
    shared = sorted(set(current) & set(baseline))
    new_to_baseline = sorted(set(current) - set(baseline))
    missing_from_current = sorted(set(baseline) - set(current))

    lines: list[str] = []
    regressed: list[str] = []
    for package in shared:
        cur = current[package]
        base = baseline[package]
        delta = cur - base
        lines.append(
            f"{package}: baseline={base:.4f} current={cur:.4f} delta={delta:+.4f}"
        )
        # Scores are rounded to 4 places (see `scores`), but plain float subtraction
        # reintroduces binary-fraction error (e.g. 0.59 - 0.6 == -0.010000000000000009),
        # so a drop of exactly `tolerance` can miss its own boundary. Rounding the delta
        # to that same precision before comparing keeps the boundary exact.
        if round(delta, 4) < -tolerance:
            regressed.append(package)

    for package in new_to_baseline:
        lines.append(f"{package}: new (current={current[package]:.4f})")

    for package in missing_from_current:
        lines.append(
            f"{package}: missing from current results (baseline={baseline[package]:.4f})"
        )

    message = "\n".join(lines) if lines else "No packages to compare."
    if regressed:
        message = f"Mutation score dropped for: {', '.join(regressed)}\n{message}"
        return 1, message
    return 0, message


def _read_results(path: str | None) -> str:
    """Read a mutmut results listing from a file, or stdin when ``path`` is None."""
    if path is None:
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def _read_baseline(path: str) -> dict[str, float]:
    """Read a baseline JSON file, treating a missing file as an empty baseline."""
    baseline_path = Path(path)
    if not baseline_path.exists():
        return {}
    return json.loads(baseline_path.read_text(encoding="utf-8"))


def _write_scores(path: str, current: Mapping[str, float]) -> None:
    """Write scores as sorted, indented JSON, matching the baseline file's style."""
    Path(path).write_text(
        json.dumps(dict(sorted(current.items())), indent=2) + "\n", encoding="utf-8"
    )


def _cmd_score(args: argparse.Namespace) -> int:
    """Print the current scores as JSON."""
    current = scores(parse_results(_read_results(args.results)))
    print(json.dumps(dict(sorted(current.items())), indent=2))
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    """Compare current scores to the baseline and writes the current scores out."""
    current = scores(parse_results(_read_results(args.results)))
    baseline = _read_baseline(args.baseline)
    exit_code, message = compare(current, baseline, tolerance=args.tolerance)
    print(message)
    _write_scores(args.write, current)
    return exit_code


def _cmd_update(args: argparse.Namespace) -> int:
    """Write the current scores as the new baseline, raising values only by default."""
    current = scores(parse_results(_read_results(args.results)))
    if args.allow_lower:
        new_baseline = dict(current)
    else:
        new_baseline = dict(_read_baseline(args.baseline))
        for package, value in current.items():
            existing = new_baseline.get(package)
            if existing is None or value > existing:
                new_baseline[package] = value
    _write_scores(args.baseline, new_baseline)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and dispatches to the ``score``/``check``/``update`` command.

    Args:
        argv: Command-line arguments, excluding the program name. Defaults to
            ``sys.argv[1:]``.

    Returns:
        The process exit code: 0 on success, 1 when ``check`` finds a regression.
    """
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0] if __doc__ else None
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    score_parser = subparsers.add_parser(
        "score", help="Print current mutation scores as JSON."
    )
    score_parser.add_argument(
        "results",
        nargs="?",
        default=None,
        help="Path to a 'mutmut results --all' listing. Reads stdin when omitted.",
    )
    score_parser.set_defaults(func=_cmd_score)

    check_parser = subparsers.add_parser(
        "check",
        help="Compare current scores to the baseline; exit 1 on any regression.",
    )
    check_parser.add_argument(
        "baseline",
        nargs="?",
        default="tests/mutation-baseline.json",
        help="Path to the baseline JSON file.",
    )
    check_parser.add_argument(
        "--results",
        default=None,
        help="Path to a 'mutmut results --all' listing. Reads stdin when omitted.",
    )
    check_parser.add_argument(
        "--write",
        required=True,
        help="Path to write the current scores JSON to, for the workflow to upload.",
    )
    check_parser.add_argument(
        "--tolerance",
        type=float,
        default=0.0,
        help="Maximum score drop that does not count as a regression (default: 0.0).",
    )
    check_parser.set_defaults(func=_cmd_check)

    update_parser = subparsers.add_parser(
        "update",
        help="Write current scores as the new baseline (raises values only, by default).",
    )
    update_parser.add_argument(
        "baseline",
        nargs="?",
        default="tests/mutation-baseline.json",
        help="Path to the baseline JSON file to write.",
    )
    update_parser.add_argument(
        "--results",
        default=None,
        help="Path to a 'mutmut results --all' listing. Reads stdin when omitted.",
    )
    update_parser.add_argument(
        "--allow-lower",
        action="store_true",
        help="Overwrite the baseline with current scores even where they are lower.",
    )
    update_parser.set_defaults(func=_cmd_update)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
