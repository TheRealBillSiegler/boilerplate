"""Lint every commit in a range against AGENTS.md's Commits rules.

Delegates the message-format and length rules to commitizen's ``cz check``:
``pyproject.toml``'s ``[tool.commitizen]`` section pins the type set to
AGENTS.md's Commits table and empties ``allowed_prefixes``, and this script
passes the 72-character limit (``_MESSAGE_LENGTH_LIMIT``) on the command line;
its own job is resolving which commits to check.

In CI, the range runs from the merge base of the pull request's base and head
SHAs to the head SHA, both SHAs known from the event — see
``.github/workflows/ci.yml`` (the ``commit-lint`` job, a need of the required
CI gate). Locally, the remote holding the public
repository is not always named ``origin`` (a fork or an archive clone carries
its own ``develop``), so the base defaults to the integration branch's
remote-tracking ref (``refs/remotes/*/develop``), never a hard-coded remote
name: the current branch's own upstream is used only when it already points at
that branch, since otherwise it is the branch's own pushed copy, not something
to diff against. Pass ``--base`` to override.

Usage:
    uv run python scripts/commit_lint.py [--base REF] [--head REF]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final

_REPO_ROOT: Final = Path(__file__).resolve().parent.parent
_MESSAGE_LENGTH_LIMIT: Final = 72
_INTEGRATION_BRANCH: Final = "develop"


class NoUpstreamError(RuntimeError):
    """No base ref was given and the integration branch cannot be resolved."""


def _run(argv: Sequence[str], *, repo_root: Path) -> str:
    """Run a git command and return its stripped stdout.

    Args:
        argv: The command and its arguments, e.g. ``["git", "status"]``.
        repo_root: The working directory to run it in.

    Returns:
        The command's stdout, stripped of surrounding whitespace.
    """
    result = subprocess.run(
        argv,
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return result.stdout.strip()


def _run_or_none(argv: Sequence[str], *, repo_root: Path) -> str | None:
    """Run a git command and return its stripped stdout, or None if it fails.

    Args:
        argv: The command and its arguments.
        repo_root: The working directory to run it in.

    Returns:
        The stripped stdout, or None when the command exits non-zero.
    """
    try:
        return _run(argv, repo_root=repo_root)
    except subprocess.CalledProcessError:
        return None


def _upstream_ref(repo_root: Path) -> str | None:
    """Return the current branch's upstream tracking ref, or None if unset.

    Args:
        repo_root: The repository to resolve the ref in.

    Returns:
        The short name of the upstream ref (e.g. ``origin/feature``), or
        None when the current branch has no upstream configured.
    """
    return _run_or_none(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        repo_root=repo_root,
    )


def _merge_base(ref: str, head: str, *, repo_root: Path) -> str | None:
    """Return the merge base of ``ref`` and ``head``.

    Args:
        ref: A candidate base ref.
        head: The range's head ref.
        repo_root: The repository to run in.

    Returns:
        The merge base's SHA, or None when the two share no history.
    """
    return _run_or_none(["git", "merge-base", ref, head], repo_root=repo_root)


def _find_integration_ref(repo_root: Path, *, head: str) -> str:
    """Find the remote-tracking integration branch nearest to ``head``.

    A clone often has more than one remote carrying ``develop``: a
    contributor's fork and the repository it came from, or an archive and
    the public repository. The candidate whose merge base with ``head``
    leaves the fewest commits to lint is the one ``head`` was cut from; a
    candidate that shares no history with ``head`` is skipped. Ties go to
    the first name in sort order, so the choice is deterministic.

    Args:
        repo_root: The repository to search.
        head: The range's head ref.

    Returns:
        The short name of the chosen ``refs/remotes/*/develop`` ref (e.g.
        ``public/develop``).

    Raises:
        NoUpstreamError: No such ref exists, or none shares history with
            ``head``. Pass ``--base <ref>`` instead.
    """
    refs = _run(
        [
            "git",
            "for-each-ref",
            "--format=%(refname:short)",
            f"refs/remotes/*/{_INTEGRATION_BRANCH}",
        ],
        repo_root=repo_root,
    ).splitlines()
    if not refs:
        raise NoUpstreamError(
            f"No --base given, the current branch's upstream does not point "
            f"at {_INTEGRATION_BRANCH}, and no remote-tracking "
            f"{_INTEGRATION_BRANCH} branch was found. Pass --base <ref> "
            f"explicitly."
        )
    candidates: list[tuple[int, str]] = []
    for ref in refs:
        base = _merge_base(ref, head, repo_root=repo_root)
        if base is not None:
            count = _run(
                ["git", "rev-list", "--count", f"{base}..{head}"], repo_root=repo_root
            )
            candidates.append((int(count), ref))
    if not candidates:
        raise NoUpstreamError(
            f"No --base given and no remote-tracking {_INTEGRATION_BRANCH} "
            f"branch ({', '.join(refs)}) shares history with {head}. Pass "
            f"--base <ref> explicitly."
        )
    return min(candidates)[1]


def resolve_base(
    explicit_base: str | None, *, head: str = "HEAD", repo_root: Path = _REPO_ROOT
) -> str:
    """Resolve the commit range's base ref.

    Args:
        explicit_base: A ref passed with ``--base``, or None to resolve the
            integration branch automatically.
        head: The range's head ref. The merge base is computed against this
            ref, not a hard-coded ``HEAD``, so it agrees with the range
            ``commit_lint`` actually lints.
        repo_root: The repository to resolve the ref in.

    Returns:
        The merge base of ``head`` and the resolved base ref: the commit
        both share, so the range excludes everything already on the
        integration branch.

    Raises:
        NoUpstreamError: No ``--base`` was given and the integration
            branch's remote-tracking ref does not exist or shares no history
            with ``head``. See ``_find_integration_ref``.
    """
    if explicit_base is not None:
        base_ref = explicit_base
    else:
        upstream = _upstream_ref(repo_root)
        if upstream is not None and upstream.rsplit("/", 1)[-1] == _INTEGRATION_BRANCH:
            # The branch tracks the integration branch directly: no need to
            # scan remotes, and this also covers repos with more than one
            # remote carrying a `develop` branch.
            base_ref = upstream
        else:
            # No upstream, or the upstream is the branch's own pushed copy
            # (e.g. after `git push -u origin feature`) — neither tells us
            # where the branch forked from, so find `develop` directly.
            base_ref = _find_integration_ref(repo_root, head=head)
    return _run(["git", "merge-base", base_ref, head], repo_root=repo_root)


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    """Parse this script's command-line arguments.

    Args:
        argv: The arguments to parse, or None to read `sys.argv`.

    Returns:
        The parsed arguments: `base` and `head`.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base",
        help=(
            "Git ref to diff against (default: the integration branch's "
            "remote-tracking ref)."
        ),
    )
    parser.add_argument(
        "--head", default="HEAD", help="Git ref for the range's head (default: HEAD)."
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Resolve the commit range and run `cz check` over it.

    Args:
        argv: The arguments to parse, or None to read `sys.argv`.

    Returns:
        The process exit code: `cz check`'s own code, or 2 when the range
        cannot be resolved.
    """
    args = _parse_args(argv)
    try:
        base = resolve_base(args.base, head=args.head)
    except NoUpstreamError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    rev_range = f"{base}..{args.head}"
    commit_count = _run(["git", "rev-list", "--count", rev_range], repo_root=_REPO_ROOT)
    if commit_count == "0":
        print(f"No commits in {rev_range}; nothing to lint.")
        return 0

    print(f"Linting commits in {rev_range}", flush=True)
    result = subprocess.run(
        [
            "cz",
            "check",
            "--rev-range",
            rev_range,
            "--message-length-limit",
            str(_MESSAGE_LENGTH_LIMIT),
        ],
        cwd=_REPO_ROOT,
        check=False,
    )
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
