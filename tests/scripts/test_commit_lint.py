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


def _git(cwd: Path, *args: str) -> str:
    """Run a git command in ``cwd`` and return its stripped stdout.

    Raises:
        subprocess.CalledProcessError: If git exits non-zero.
    """
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _init_repo(path: Path, branch: str) -> None:
    """Initialise a repo on `branch` with a committer identity."""
    path.mkdir()
    _git(path, "init", "-b", branch)
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test")


def _commit_file(repo: Path, name: str, message: str) -> None:
    """Write `name`, stage it and commit with `message`."""
    (repo / name).write_text(name, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "-m", message)


def _rev_parse(repo: Path, ref: str) -> str:
    """Return the SHA `ref` resolves to in `repo`."""
    return _git(repo, "rev-parse", ref)


def _clone_of_seeded_remote(tmp_path: Path) -> tuple[Path, str]:
    """Clone a seeded `develop` remote and return the clone and the seed SHA."""
    remote = tmp_path / "remote"
    _init_repo(remote, "develop")
    _commit_file(remote, "a.txt", "chore: seed")
    local = tmp_path / "local"
    _git(tmp_path, "clone", str(remote), str(local))
    _git(local, "config", "user.email", "test@example.com")
    _git(local, "config", "user.name", "Test")
    return local, _rev_parse(remote, "HEAD")


@pytest.fixture
def repo_with_upstream(tmp_path: Path) -> tuple[Path, str]:
    """Build a local repo with a remote-tracking branch two commits ahead.

    Returns:
        The repo's working directory and the SHA of the commit both branches
        share (what ``resolve_base`` should return).
    """
    local, shared_sha = _clone_of_seeded_remote(tmp_path)
    _git(local, "checkout", "-b", "feature", "--track", "origin/develop")
    _commit_file(local, "b.txt", "feat: add b")

    return local, shared_sha


@pytest.fixture
def repo_with_remote_develop_and_no_upstream(tmp_path: Path) -> tuple[Path, str]:
    """Build a repo whose remote has `develop` but whose branch has no upstream.

    Mirrors a branch created before its first push: there is nothing to
    diff against except the remote's own `develop`.

    Returns:
        The repo's working directory and the SHA of the commit both branches
        share (what ``resolve_base`` should return).
    """
    local, shared_sha = _clone_of_seeded_remote(tmp_path)
    _git(local, "checkout", "-b", "feature")  # no --track: no upstream at all
    _commit_file(local, "b.txt", "feat: add b")

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
    local, shared_sha = _clone_of_seeded_remote(tmp_path)
    _git(local, "checkout", "-b", "feature")
    _commit_file(local, "b.txt", "feat: add b")
    # Simulate `git push -u origin feature` without a real remote round trip.
    _git(local, "update-ref", "refs/remotes/origin/feature", "HEAD")
    _git(local, "config", "branch.feature.remote", "origin")
    _git(local, "config", "branch.feature.merge", "refs/heads/feature")

    return local, shared_sha


@pytest.fixture
def repo_whose_branch_name_ends_in_develop(tmp_path: Path) -> tuple[Path, str]:
    """Build a repo whose branch `topic/develop` tracks its own pushed copy.

    The upstream's last path segment is ``develop``, but it is the branch's
    own copy, not the integration branch.

    Returns:
        The repo's working directory and the SHA of the commit both branches
        share (what ``resolve_base`` should return).
    """
    local, shared_sha = _clone_of_seeded_remote(tmp_path)
    _git(local, "checkout", "-b", "topic/develop")
    _commit_file(local, "b.txt", "feat: add b")
    _git(local, "update-ref", "refs/remotes/origin/topic/develop", "HEAD")
    _git(local, "config", "branch.topic/develop.remote", "origin")
    _git(local, "config", "branch.topic/develop.merge", "refs/heads/topic/develop")

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
        _init_repo(repo, "main")
        _commit_file(repo, "a.txt", "chore: seed")

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
        # Using origin/feature (== HEAD) as the base would return HEAD itself
        # rather than the shared ancestor.
        assert commit_lint.resolve_base(None, repo_root=local) == shared_sha

    def test_a_branch_named_like_develop_tracking_its_own_copy_is_not_the_base(
        self, repo_whose_branch_name_ends_in_develop: tuple[Path, str]
    ) -> None:
        """An upstream counts as the base only when it is the integration branch."""
        local, shared_sha = repo_whose_branch_name_ends_in_develop
        assert commit_lint.resolve_base(None, repo_root=local) == shared_sha

    def test_a_remote_develop_with_no_shared_history_is_skipped(
        self, repo_with_remote_develop_and_no_upstream: tuple[Path, str]
    ) -> None:
        local, shared_sha = repo_with_remote_develop_and_no_upstream
        unrelated = local.parent / "unrelated_remote"
        _init_repo(unrelated, "develop")
        _commit_file(unrelated, "z.txt", "chore: seed")
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
        _commit_file(upstream, "c.txt", "feat: add c")
        newer_develop = _rev_parse(upstream, "HEAD")
        _git(local, "remote", "add", "upstream", str(upstream))
        _git(local, "fetch", "upstream")
        _git(local, "checkout", "--no-track", "-b", "from-upstream", "upstream/develop")
        _commit_file(local, "d.txt", "feat: add d")

        assert commit_lint.resolve_base(None, repo_root=local) == newer_develop

    def test_no_remote_develop_sharing_history_raises_a_clear_error(
        self, repo_with_remote_develop_and_no_upstream: tuple[Path, str]
    ) -> None:
        local, _ = repo_with_remote_develop_and_no_upstream
        _git(local, "checkout", "--orphan", "unrelated")
        _git(local, "rm", "-rf", ".")
        _commit_file(local, "z.txt", "chore: unrelated root")

        with pytest.raises(commit_lint.NoUpstreamError, match="--base"):
            commit_lint.resolve_base(None, repo_root=local)

    def test_merge_base_is_computed_against_the_given_head_not_local_head(
        self, repo_with_upstream: tuple[Path, str]
    ) -> None:
        local, _ = repo_with_upstream
        # A commit with no history in common with develop at all.
        _git(local, "checkout", "--orphan", "unrelated")
        _git(local, "rm", "-rf", ".")
        _commit_file(local, "z.txt", "chore: unrelated root")
        unrelated_sha = _rev_parse(local, "HEAD")
        _git(local, "checkout", "feature")  # local HEAD is an ancestor of develop again

        # If resolve_base diffed against literal HEAD instead of the given
        # `head`, this would silently succeed against the wrong commit.
        with pytest.raises(subprocess.CalledProcessError):
            commit_lint.resolve_base(None, head=unrelated_sha, repo_root=local)


class TestMain:
    """`main` reports a range it cannot resolve instead of raising."""

    def test_an_unresolvable_base_exits_2(self) -> None:
        """The `main` docstring reserves exit code 2 for an unresolvable range."""
        assert commit_lint.main(["--base", "no-such-ref-anywhere"]) == 2

    def test_an_unresolvable_base_names_the_range_on_stderr(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        commit_lint.main(["--base", "no-such-ref-anywhere"])

        assert (
            "error: cannot resolve no-such-ref-anywhere..HEAD"
            in capsys.readouterr().err
        )


class TestAllowedPrefixes:
    """This repo's `allowed_prefixes` override in `pyproject.toml`.

    cz's own message-format checking is not retested here (see the module
    docstring) — only that this repo's specific override actually closes
    the fixup!/squash!/amend!/Revert bypass its stock default leaves open.
    """

    @staticmethod
    def _repo_with_project_schema(tmp_path: Path) -> Path:
        """Build a repo that carries this project's `pyproject.toml` and one commit."""
        repo = tmp_path / "repo"
        _init_repo(repo, "develop")
        (repo / "pyproject.toml").write_text(
            (_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        _git(repo, "add", "pyproject.toml")
        _git(repo, "commit", "-m", "chore: seed")
        return repo

    @staticmethod
    def _cz_check_last_commit(repo: Path) -> subprocess.CompletedProcess[str]:
        """Run `cz check` over the repo's last commit."""
        return subprocess.run(
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

    def test_a_conforming_commit_passes_the_project_schema(
        self, tmp_path: Path
    ) -> None:
        """Positive control: the schema loads, so a fixup failure is about the fixup."""
        repo = self._repo_with_project_schema(tmp_path)
        _git(repo, "commit", "--allow-empty", "-m", "feat: whatever")

        result = self._cz_check_last_commit(repo)

        assert result.returncode == 0, result.stdout + result.stderr

    def test_a_fixup_commit_fails_the_project_schema(self, tmp_path: Path) -> None:
        repo = self._repo_with_project_schema(tmp_path)
        _git(repo, "commit", "--allow-empty", "-m", "fixup! feat: whatever")

        result = self._cz_check_last_commit(repo)

        assert result.returncode != 0, result.stdout + result.stderr
