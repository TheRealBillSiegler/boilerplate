"""Checks that a PR's added tests actually discriminate the change they ship with.

Rule: when a PR changes anything under ``src/`` and adds test functions under
``tests/``, at least one added test must fail or error when run against the
base commit's ``src/``. If every added test already passes on the base, none
of them ever went red, so none of them proves the change does anything — this
is the mechanical form of red-first (write the failing test first, then make
it pass): a regression test only counts once it has been watched to fail
against the code it is meant to guard.

Everywhere in this script, "base" means the merge base — the commit where
head forked from the base ref, from ``git merge-base <base> <head>`` —
never the base ref's own current tip. A base-branch commit that lands after
the PR forked is not part of the PR's own diff: it must not count as
something the PR changed, and the PR's added tests must not be judged
against a ``src/`` tree that includes it. ``--base`` and ``--head`` are git
refs, resolved once against this merge base at the start of a run.

Head's test sources are read from the working tree, not from a git ref: the
working tree must already be checked out at ``--head`` or at the merge of
``--base`` and ``--head`` (on ``pull_request`` events, ``actions/checkout``
gives the merge commit — see the ``--head`` help text). Base's test and
``src/`` sources are read from git directly, so the base ref itself never
needs to be checked out.

Three deliberate limits:

* A PR that only moves or renames tests, without touching ``src/``, is not
  judged — ``src_changed`` is false, so the check reports "nothing to
  discriminate" rather than running anything.
* A PR whose new tests need a dependency the base commit does not have will
  see those tests fail or error out on base (a module-level import that
  the base tree can't resolve is a collection error; the same import
  raised from inside a test body is a plain test failure). Either way it
  still counts as having gone red: the check cannot tell "failed because
  the change is missing" apart from "failed because the environment is
  missing", and treating both as red is the safer of the two mistakes.
* A test module that is renamed or moved is matched back to its old path
  (via git's own rename detection) so only its genuinely new node ids count
  as added. Renaming a test *function* within a file that keeps the same
  path is not caught the same way: the new name looks added and the old
  name simply disappears, because the script diffs identifiers inside a
  file, not their history across it.

Usage:
    uv run python scripts/new_tests_go_red.py --base <ref> [--head <ref>]
"""

from __future__ import annotations

import argparse
import ast
import os
import subprocess
import sys
import tarfile
import tempfile
import xml.etree.ElementTree as ET
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Final

_REPO_ROOT: Final = Path(__file__).resolve().parent.parent

# Worse-outcome ranking for folding a parametrized test's instances into one
# outcome per node id: skipped outranks a plain pass (it proves nothing
# either way), a failure outranks a skip, and an error outranks a failure.
_SEVERITY: Final[dict[str, int]] = {
    "passed": 0,
    "skipped": 1,
    "failed": 2,
    "error": 3,
}


def test_functions(source: str) -> set[str]:
    """Lists the test node ids a test module defines, relative to the module.

    Only ``def``/``async def`` names starting with ``test_`` count, and only
    at two levels: directly inside the module, or directly inside a class
    whose name starts with ``Test``. Nested functions (defined inside another
    function) are ignored, matching pytest's own collection rules.

    Args:
        source: The test module's source code.

    Returns:
        Node ids: ``"test_x"`` for a module-level test function, or
        ``"TestClass::test_y"`` for a method of a ``Test*`` class.
    """
    tree = ast.parse(source)
    node_ids: set[str] = set()
    for node in tree.body:
        if isinstance(
            node, ast.FunctionDef | ast.AsyncFunctionDef
        ) and node.name.startswith("test_"):
            node_ids.add(node.name)
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for member in node.body:
                if isinstance(
                    member, ast.FunctionDef | ast.AsyncFunctionDef
                ) and member.name.startswith("test_"):
                    node_ids.add(f"{node.name}::{member.name}")
    return node_ids


def added_tests(base_source: str | None, head_source: str) -> set[str]:
    """Find the test node ids a module gained between base and head.

    Args:
        base_source: The module's source at the base commit, or None when
            the file does not exist there (it is new at head, or is the
            target of a rename/copy git could not match back to an old
            path).
        head_source: The module's source at head.

    Returns:
        Node ids present at head but not at base. Every node id counts as
        added when the file itself is new.
    """
    head_ids = test_functions(head_source)
    if base_source is None:
        return head_ids
    return head_ids - test_functions(base_source)


def verdict(results: Mapping[str, str], src_changed: bool) -> tuple[int, str]:
    """Decides whether a PR's added tests proved they discriminate the change.

    Args:
        results: Each added test's node id mapped to its outcome running
            against the base commit's ``src/``: "passed", "skipped",
            "failed" or "error".
        src_changed: Whether the PR touches anything under ``src/``.

    Returns:
        A tuple of the process exit code and a human-readable message.
        Exit 0 with "nothing to discriminate" when src_changed is False or
        results is empty. Exit 1 only when at least one added test passed
        on base and none failed or errored there — none of them ever went
        red. Exit 0 otherwise: naming base-passing tests as a warning and
        base-skipped tests as informational, since a skip is neither red
        nor a passing proof that the test doesn't discriminate.
    """
    if not src_changed or not results:
        return (
            0,
            "Nothing to discriminate: no added tests to run against the base "
            "commit's src/.",
        )

    lines = [f"  {node_id}: {outcome}" for node_id, outcome in sorted(results.items())]
    passed_on_base = sorted(
        node_id for node_id, outcome in results.items() if outcome == "passed"
    )
    skipped_on_base = sorted(
        node_id for node_id, outcome in results.items() if outcome == "skipped"
    )
    went_red = any(outcome in ("failed", "error") for outcome in results.values())

    if not went_red and passed_on_base:
        header = "None of the added tests fail against the base commit's src/ — they never went red:"
        return 1, "\n".join([header, *lines])

    message_lines = ["Added tests vs. the base commit's src/:", *lines]
    if passed_on_base:
        message_lines.append("")
        message_lines.append(
            "WARNING: these passed on base too, so they don't discriminate the change:"
        )
        message_lines.extend(f"  {node_id}" for node_id in passed_on_base)
    if skipped_on_base:
        message_lines.append("")
        message_lines.append(
            "Skipped on base (neither a pass nor red, so they prove nothing either way):"
        )
        message_lines.extend(f"  {node_id}" for node_id in skipped_on_base)
    return 0, "\n".join(message_lines)


def parse_junit_outcomes(xml_text: str) -> dict[str, str]:
    """Folds a pytest junit report's testcases into one outcome per base node.

    A parametrized test reports one ``<testcase>`` per instance, named
    ``"test_x[param]"``. This strips the ``[param]`` suffix and combines the
    remaining instances for the same node: "error" if any instance errored,
    else "failed" if any instance failed, else "skipped" if any instance
    was skipped, else "passed".

    Args:
        xml_text: A pytest ``--junitxml`` report, as ``<testsuites>`` XML.

    Returns:
        A mapping from ``"<classname>::<name>"`` (junit's own id shape, with
        the parametrize suffix stripped from name) to "passed", "skipped",
        "failed" or "error".
    """
    root = ET.fromstring(xml_text)
    outcomes: dict[str, str] = {}
    for testcase in root.iter("testcase"):
        classname = testcase.get("classname", "")
        name = testcase.get("name", "")
        base_name = name.split("[", 1)[0]
        key = f"{classname}::{base_name}"
        if testcase.find("error") is not None:
            outcome = "error"
        elif testcase.find("failure") is not None:
            outcome = "failed"
        elif testcase.find("skipped") is not None:
            outcome = "skipped"
        else:
            outcome = "passed"
        previous = outcomes.get(key)
        outcomes[key] = outcome if previous is None else _worse(previous, outcome)
    return outcomes


def _worse(first: str, second: str) -> str:
    """Return whichever of two outcomes ranks as more red.

    Args:
        first: An outcome: "passed", "skipped", "failed" or "error".
        second: An outcome: "passed", "skipped", "failed" or "error".

    Returns:
        Whichever of the two outranks the other in `_SEVERITY`.
    """
    return first if _SEVERITY[first] >= _SEVERITY[second] else second


def resolve_outcomes(
    added_ids: set[str], junit_outcomes: Mapping[str, str]
) -> dict[str, str]:
    """Map this script's ``<path>::<id>`` node ids to their junit outcome.

    Bridges this script's node-id shape (a file path plus an
    ``ast``-derived id) to junit's shape (a dotted ``classname`` plus a bare
    ``name``, already folded by `parse_junit_outcomes`). A node id absent
    from the report means its module failed to collect against the base
    tree — for example, an added test that imports something the base
    commit's src/ doesn't have yet. That is still red, so it resolves to
    "error" rather than being silently dropped. The report may also contain
    outcomes for node ids that were not added; those are simply ignored.

    Args:
        added_ids: Node ids in ``"<path>::<id>"`` form, one per added test.
        junit_outcomes: The ``"<classname>::<name>"`` outcomes produced by
            `parse_junit_outcomes`.

    Returns:
        A mapping from each added node id to "passed", "skipped", "failed"
        or "error".
    """
    resolved: dict[str, str] = {}
    for node_id in added_ids:
        path, _sep, test_id = node_id.partition("::")
        module = path.removesuffix(".py").replace("/", ".").replace("\\", ".")
        if "::" in test_id:
            class_name, method_name = test_id.split("::", 1)
            junit_key = f"{module}.{class_name}::{method_name}"
        else:
            junit_key = f"{module}::{test_id}"
        resolved[node_id] = junit_outcomes.get(junit_key, "error")
    return resolved


def _merge_base(base: str, head: str) -> str:
    """Resolve the fork point where head diverged from base.

    Args:
        base: The PR's base ref.
        head: The PR's head ref.

    Returns:
        The merge-base commit's SHA — what every other function in this
        script means by "base".
    """
    result = subprocess.run(
        ["git", "merge-base", base, head],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return result.stdout.strip()


def _changed_files(base: str, head: str) -> list[str]:
    """List the paths that differ between two git refs.

    Args:
        base: The older ref (the merge base, not necessarily the base
            ref's own tip).
        head: The newer ref.

    Returns:
        Repo-relative paths, forward-slashed, as `git diff --name-only`
        reports them.
    """
    result = subprocess.run(
        ["git", "diff", "--name-only", base, head],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def _changed_test_modules(base: str, head: str) -> list[tuple[str, str | None]]:
    """List changed test modules, paired with where to read their base source.

    Runs ``git diff --name-status -M`` scoped to ``tests/`` so a renamed or
    moved test module is matched back to its old path (an ``R`` row) or, for
    a copy, its source path (a ``C`` row) — either way the module is judged
    against its own prior source rather than treated as freshly added. A
    module deleted at head is skipped: there is no head source to compare.

    Args:
        base: The older ref (the merge base).
        head: The newer ref.

    Returns:
        Pairs of ``(head_path, base_path)`` for every ``.py`` test module
        that changed and still exists at head. ``base_path`` is None for a
        module with no counterpart at base — added fresh, not a rename or
        copy target.
    """
    result = subprocess.run(
        ["git", "diff", "--name-status", "-M", base, head, "--", "tests"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    pairs: list[tuple[str, str | None]] = []
    for line in result.stdout.splitlines():
        if not line:
            continue
        fields = line.split("\t")
        status = fields[0]
        if status.startswith("D"):
            continue  # Deleted at head: nothing to compare.
        if status.startswith(("R", "C")):
            old_path, new_path = fields[1], fields[2]
            if new_path.endswith(".py"):
                pairs.append((new_path, old_path))
        else:
            path = fields[1]
            if path.endswith(".py"):
                pairs.append((path, path if status.startswith("M") else None))
    return pairs


def _read_at_ref(ref: str, path: str) -> str | None:
    """Read a repo-relative file's content at a git ref.

    Args:
        ref: The git ref to read from.
        path: The repo-relative path to read.

    Returns:
        The file's content, or None when the path does not exist at ref.
    """
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def _run_against_base(
    base: str, test_files: set[str], added_ids: set[str]
) -> dict[str, str]:
    """Run the changed test files against the base src/ and reports outcomes.

    Exports the base tree's ``src/`` into a scratch directory and prepends it
    to ``PYTHONPATH``, ahead of this worktree's own editable install, so the
    added tests import the old code without a second install. Head's test
    files are used as-is from the working tree; only ``src/`` is swapped.

    Running whole files rather than every added node id keeps the pytest
    command line bounded even when a PR adds many parametrized cases;
    `resolve_outcomes` already tolerates a report containing outcomes for
    node ids beyond the ones it looks up.

    Args:
        base: The base commit's git ref (the merge base).
        test_files: Repo-relative test file paths to run.
        added_ids: Node ids in ``"<path>::<id>"`` form whose outcome to
            extract from the report afterward.

    Returns:
        A mapping from each added node id to "passed", "skipped", "failed"
        or "error". Every id resolves to "error" when pytest never produced
        a report (for example, a crash before collection).
    """
    with tempfile.TemporaryDirectory(prefix="new-tests-go-red-") as tmp_name:
        tmp = Path(tmp_name)
        archive_path = tmp / "base-src.tar"
        subprocess.run(
            [
                "git",
                "archive",
                "--format=tar",
                "--output",
                str(archive_path),
                base,
                "src",
            ],
            cwd=_REPO_ROOT,
            check=True,
        )
        with tarfile.open(archive_path) as tar:
            tar.extractall(tmp, filter="data")

        report_path = tmp / "report.xml"
        command = [
            "uv",
            "run",
            "pytest",
            *sorted(test_files),
            "-p",
            "no:cacheprovider",
            "-n0",
            "-q",
            "--no-header",
            f"--junitxml={report_path}",
        ]
        print(f"Running: {' '.join(command)}", flush=True)

        pythonpath = str(tmp / "src")
        existing_pythonpath = os.environ.get("PYTHONPATH")
        merged_pythonpath = (
            pythonpath
            if not existing_pythonpath
            else f"{pythonpath}{os.pathsep}{existing_pythonpath}"
        )
        env = {**os.environ, "PYTHONPATH": merged_pythonpath}
        subprocess.run(command, cwd=_REPO_ROOT, env=env, check=False)

        if not report_path.is_file():
            return dict.fromkeys(added_ids, "error")
        junit_outcomes = parse_junit_outcomes(report_path.read_text(encoding="utf-8"))
        return resolve_outcomes(added_ids, junit_outcomes)


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    """Parse this script's command-line arguments.

    Args:
        argv: The arguments to parse, or None to read `sys.argv`.

    Returns:
        The parsed arguments: `base` and `head`.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base", required=True, help="Git ref for the PR's base commit."
    )
    parser.add_argument(
        "--head",
        default="HEAD",
        help=(
            "Git ref for the PR's head commit (default: HEAD). Test sources "
            "at head are read from the working tree, not from this ref, so "
            "the tree must already be checked out at --head or at the merge "
            "of --base and --head (actions/checkout gives the merge commit "
            "on pull_request events)."
        ),
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the check and prints its verdict.

    Args:
        argv: The arguments to parse, or None to read `sys.argv`.

    Returns:
        The process exit code: 0 when the added tests discriminate the
        change (or there was nothing to judge), 1 when none of them do.
    """
    args = _parse_args(argv)
    base = _merge_base(args.base, args.head)
    changed = _changed_files(base, args.head)
    src_changed = any(path.startswith("src/") for path in changed)

    added_ids: set[str] = set()
    test_files: set[str] = set()
    for head_path, base_path in _changed_test_modules(base, args.head):
        head_file = _REPO_ROOT / head_path
        if not head_file.is_file():
            continue  # Deleted at head: nothing to compare.
        head_source = head_file.read_text(encoding="utf-8")
        base_source = _read_at_ref(base, base_path) if base_path else None
        new_ids = added_tests(base_source, head_source)
        if new_ids:
            test_files.add(head_path)
            added_ids.update(f"{head_path}::{test_id}" for test_id in new_ids)

    results: dict[str, str] = {}
    if added_ids and src_changed:
        results = _run_against_base(base, test_files, added_ids)

    code, message = verdict(results, src_changed)
    print(message)
    return code


if __name__ == "__main__":
    sys.exit(main())
