"""Tests for scripts/commit_lint.py's commit-range resolution.

Most of the message-format and length rules are enforced by ``cz check``
itself (see ``pyproject.toml``'s ``[tool.commitizen]`` config), a
third-party tool this repository does not re-test. The one exception is
``allowed_prefixes``: this repo overrides cz's default there, and that
override is our config choice to get right, so it gets its own regression
test below.
"""

import importlib.util
import subprocess
from pathlib import Path

import pytest

_MODULE_PATH = (
    Path(__file__).resolve().parent.parent.parent / "scripts" / "commit_lint.py"
)
_REPO_ROOT = _MODULE_PATH.parent.parent
_SPEC = importlib.util.spec_from_file_location("commit_lint", _MODULE_PATH)
assert _SPEC is not None
assert _SPEC.loader is not None
commit_lint = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(commit_lint)


def _git(cwd: Path, *args: str) -> None:
    """Run a git command in ``cwd``, raising on failure."""
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def repo_with_upstream(tmp_path: Path) -> tuple[Path, str]:
    """Build a local repo with a remote-tracking branch two commits ahead.

    Returns:
        The repo's working directory and the SHA of the commit both branches
        share (what ``resolve_base`` should return).
    """
    remote = tmp_path / "remote"
    remote.mkdir()
    _git(remote, "init", "-b", "develop")
    _git(remote, "config", "user.email", "test@example.com")
    _git(remote, "config", "user.name", "Test")
    (remote / "a.txt").write_text("a", encoding="utf-8")
    _git(remote, "add", "a.txt")
    _git(remote, "commit", "-m", "chore: seed")
    shared_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=remote,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    local = tmp_path / "local"
    _git(tmp_path, "clone", str(remote), str(local))
    _git(local, "config", "user.email", "test@example.com")
    _git(local, "config", "user.name", "Test")
    _git(local, "checkout", "-b", "feature", "--track", "origin/develop")
    (local / "b.txt").write_text("b", encoding="utf-8")
    _git(local, "add", "b.txt")
    _git(local, "commit", "-m", "feat: add b")

    return local, shared_sha


def _rev_parse(repo: Path, ref: str) -> str:
    """Return the SHA `ref` resolves to in `repo`."""
    return subprocess.run(
        ["git", "rev-parse", ref],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def repo_with_remote_develop_and_no_upstream(tmp_path: Path) -> tuple[Path, str]:
    """Build a repo whose remote has `develop` but whose branch has no upstream.

    Mirrors a branch created before its first push: there is nothing to
    diff against except the remote's own `develop`.

    Returns:
        The repo's working directory and the SHA of the commit both branches
        share (what ``resolve_base`` should return).
    """
    remote = tmp_path / "remote"
    remote.mkdir()
    _git(remote, "init", "-b", "develop")
    _git(remote, "config", "user.email", "test@example.com")
    _git(remote, "config", "user.name", "Test")
    (remote / "a.txt").write_text("a", encoding="utf-8")
    _git(remote, "add", "a.txt")
    _git(remote, "commit", "-m", "chore: seed")
    shared_sha = _rev_parse(remote, "HEAD")

    local = tmp_path / "local"
    _git(tmp_path, "clone", str(remote), str(local))
    _git(local, "config", "user.email", "test@example.com")
    _git(local, "config", "user.name", "Test")
    _git(local, "checkout", "-b", "feature")  # no --track: no upstream at all
    (local / "b.txt").write_text("b", encoding="utf-8")
    _git(local, "add", "b.txt")
    _git(local, "commit", "-m", "feat: add b")

    return local, shared_sha


@pytest.fixture
def repo_with_own_remote_copy_as_upstream(tmp_path: Path) -> tuple[Path, str]:
    """Build a repo whose upstream is the branch's own pushed copy, not develop.

    Mirrors ``git push -u origin feature``: the branch's upstream then names
    its own remote copy, which never diffs meaningfully against itself.

    Returns:
        The repo's working directory and the SHA of the commit both branches
        share (what ``resolve_base`` should return).
    """
    remote = tmp_path / "remote"
    remote.mkdir()
    _git(remote, "init", "-b", "develop")
    _git(remote, "config", "user.email", "test@example.com")
    _git(remote, "config", "user.name", "Test")
    (remote / "a.txt").write_text("a", encoding="utf-8")
    _git(remote, "add", "a.txt")
    _git(remote, "commit", "-m", "chore: seed")
    shared_sha = _rev_parse(remote, "HEAD")

    local = tmp_path / "local"
    _git(tmp_path, "clone", str(remote), str(local))
    _git(local, "config", "user.email", "test@example.com")
    _git(local, "config", "user.name", "Test")
    _git(local, "checkout", "-b", "feature")
    (local / "b.txt").write_text("b", encoding="utf-8")
    _git(local, "add", "b.txt")
    _git(local, "commit", "-m", "feat: add b")
    # Simulate `git push -u origin feature` without a real remote round trip.
    _git(local, "update-ref", "refs/remotes/origin/feature", "HEAD")
    _git(local, "config", "branch.feature.remote", "origin")
    _git(local, "config", "branch.feature.merge", "refs/heads/feature")

    return local, shared_sha


class TestResolveBase:
    def test_auto_detects_the_upstream_tracking_branch(
        self, repo_with_upstream: tuple[Path, str]
    ) -> None:
        local, shared_sha = repo_with_upstream
        assert commit_lint.resolve_base(None, repo_root=local) == shared_sha

    def test_explicit_base_wins_over_the_upstream_tracking_branch(
        self, repo_with_upstream: tuple[Path, str]
    ) -> None:
        local, shared_sha = repo_with_upstream
        # HEAD~0 (the feature commit itself) as an explicit base: the merge
        # base of HEAD and HEAD is HEAD, not the shared ancestor.
        head_sha = _rev_parse(local, "HEAD")
        assert commit_lint.resolve_base("HEAD", repo_root=local) == head_sha
        assert commit_lint.resolve_base("HEAD", repo_root=local) != shared_sha

    def test_no_explicit_base_and_no_upstream_raises_a_clear_error(
        self, tmp_path: Path
    ) -> None:
        repo = tmp_path / "orphan"
        repo.mkdir()
        _git(repo, "init", "-b", "main")
        _git(repo, "config", "user.email", "test@example.com")
        _git(repo, "config", "user.name", "Test")
        (repo / "a.txt").write_text("a", encoding="utf-8")
        _git(repo, "add", "a.txt")
        _git(repo, "commit", "-m", "chore: seed")

        with pytest.raises(commit_lint.NoUpstreamError, match="--base"):
            commit_lint.resolve_base(None, repo_root=repo)

    def test_no_upstream_falls_back_to_the_remote_develop_branch(
        self, repo_with_remote_develop_and_no_upstream: tuple[Path, str]
    ) -> None:
        local, shared_sha = repo_with_remote_develop_and_no_upstream
        assert commit_lint.resolve_base(None, repo_root=local) == shared_sha

    def test_upstream_pointing_at_its_own_copy_is_not_used_as_the_base(
        self, repo_with_own_remote_copy_as_upstream: tuple[Path, str]
    ) -> None:
        local, shared_sha = repo_with_own_remote_copy_as_upstream
        # The buggy behaviour used `origin/feature` (== HEAD) as the base,
        # returning HEAD itself instead of the shared ancestor.
        assert commit_lint.resolve_base(None, repo_root=local) == shared_sha

    def test_a_remote_develop_with_no_shared_history_is_skipped(
        self, repo_with_remote_develop_and_no_upstream: tuple[Path, str]
    ) -> None:
        local, shared_sha = repo_with_remote_develop_and_no_upstream
        unrelated = local.parent / "unrelated_remote"
        unrelated.mkdir()
        _git(unrelated, "init", "-b", "develop")
        _git(unrelated, "config", "user.email", "test@example.com")
        _git(unrelated, "config", "user.name", "Test")
        (unrelated / "z.txt").write_text("z", encoding="utf-8")
        _git(unrelated, "add", "z.txt")
        _git(unrelated, "commit", "-m", "chore: seed")
        _git(local, "remote", "add", "unrelated", str(unrelated))
        _git(local, "fetch", "unrelated")

        assert commit_lint.resolve_base(None, repo_root=local) == shared_sha

    def test_a_fork_and_its_upstream_resolve_to_the_nearer_develop(
        self, repo_with_remote_develop_and_no_upstream: tuple[Path, str]
    ) -> None:
        # origin plays the contributor's stale fork; upstream's develop has
        # moved on, and the feature branch was cut from it.
        local, _ = repo_with_remote_develop_and_no_upstream
        upstream = local.parent / "upstream"
        _git(local.parent, "clone", str(local.parent / "remote"), str(upstream))
        _git(upstream, "config", "user.email", "test@example.com")
        _git(upstream, "config", "user.name", "Test")
        (upstream / "c.txt").write_text("c", encoding="utf-8")
        _git(upstream, "add", "c.txt")
        _git(upstream, "commit", "-m", "feat: add c")
        newer_develop = _rev_parse(upstream, "HEAD")
        _git(local, "remote", "add", "upstream", str(upstream))
        _git(local, "fetch", "upstream")
        _git(local, "checkout", "--no-track", "-b", "from-upstream", "upstream/develop")
        (local / "d.txt").write_text("d", encoding="utf-8")
        _git(local, "add", "d.txt")
        _git(local, "commit", "-m", "feat: add d")

        assert commit_lint.resolve_base(None, repo_root=local) == newer_develop

    def test_no_remote_develop_sharing_history_raises_a_clear_error(
        self, repo_with_remote_develop_and_no_upstream: tuple[Path, str]
    ) -> None:
        local, _ = repo_with_remote_develop_and_no_upstream
        _git(local, "checkout", "--orphan", "unrelated")
        _git(local, "rm", "-rf", ".")
        (local / "z.txt").write_text("z", encoding="utf-8")
        _git(local, "add", "z.txt")
        _git(local, "commit", "-m", "chore: unrelated root")

        with pytest.raises(commit_lint.NoUpstreamError, match="--base"):
            commit_lint.resolve_base(None, repo_root=local)

    def test_merge_base_is_computed_against_the_given_head_not_local_head(
        self, repo_with_upstream: tuple[Path, str]
    ) -> None:
        local, _ = repo_with_upstream
        # A commit with no history in common with develop at all.
        _git(local, "checkout", "--orphan", "unrelated")
        _git(local, "rm", "-rf", ".")
        (local / "z.txt").write_text("z", encoding="utf-8")
        _git(local, "add", "z.txt")
        _git(local, "commit", "-m", "chore: unrelated root")
        unrelated_sha = _rev_parse(local, "HEAD")
        _git(local, "checkout", "feature")  # local HEAD is an ancestor of develop again

        # If resolve_base diffed against literal HEAD instead of the given
        # `head`, this would silently succeed against the wrong commit.
        with pytest.raises(subprocess.CalledProcessError):
            commit_lint.resolve_base(None, head=unrelated_sha, repo_root=local)


class TestAllowedPrefixes:
    """This repo's `allowed_prefixes` override in `pyproject.toml`.

    cz's own message-format checking is not retested here (see the module
    docstring) — only that this repo's specific override actually closes
    the fixup!/squash!/amend!/Revert bypass its stock default leaves open.
    """

    def test_a_fixup_commit_fails_the_project_schema(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init", "-b", "develop")
        _git(repo, "config", "user.email", "test@example.com")
        _git(repo, "config", "user.name", "Test")
        (repo / "pyproject.toml").write_text(
            (_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        _git(repo, "add", "pyproject.toml")
        _git(repo, "commit", "-m", "chore: seed")
        _git(repo, "commit", "--allow-empty", "-m", "fixup! feat: whatever")

        result = subprocess.run(
            [
                "cz",
                "check",
                "--rev-range",
                "HEAD~1..HEAD",
                "--message-length-limit",
                "72",
            ],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode != 0, result.stdout + result.stderr
