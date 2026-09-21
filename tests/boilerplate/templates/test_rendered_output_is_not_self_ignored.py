"""A bundled layer's own ``.gitignore`` hides nothing the project needs.

A rendered project is a git repository from its first commit, and Copier's
update reads that repository: it refuses a dirty tree, diffs against the index,
and merges through it. A file the project's own ``.gitignore`` matches never
reaches that index, so it is invisible to every one of those steps — the user's
edits to it are unrecoverable if a later template version drops the file.

Both halves of the rule are guarded here (docs/templates-hub/versioning.md,
Authoring rules): nothing the layer renders may be ignored, and nothing the
render tells the user to commit may be ignored. The second half is checked
against the path rather than the file, because the lock file is written by a
post-generation task that these renders skip.

The planted-violation test proves the checks report what they claim to; without
it a green run cannot distinguish a clean render from a check that never looked.
"""

import subprocess
from pathlib import Path

import pytest

from tests.boilerplate.templates.conftest import LAYERS, render

IGNORED_PREFIX = "!! "
# Written by the post-generation task, and committed: the rendered README says
# so, and a reproducible install depends on it.
COMMITTED_LOCKFILE = "uv.lock"


def _git(project: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    # check=False: callers read the exit status themselves, and `check-ignore`
    # returns 1 for the ordinary "no path matched" answer this module wants.
    return subprocess.run(
        ["git", "-c", "core.autocrlf=false", "-C", str(project), *args],
        capture_output=True,
        check=False,
    )


def _init_repo(project: Path) -> None:
    """Initialize a repository in `project` so git resolves its ignore rules."""
    _git(project, "init", "-q", "-b", "main").check_returncode()


def _self_ignored_paths(project: Path) -> list[str]:
    """List the paths in `project` that the project's own `.gitignore` matches.

    Args:
        project: A rendered project directory with a repository initialized.

    Returns:
        Repository-relative paths, as git prints them; ignored directories are
        collapsed to a single trailing-slash entry.
    """
    result = _git(project, "status", "--porcelain", "--ignored")
    result.check_returncode()
    return [
        line[len(IGNORED_PREFIX) :]
        for line in result.stdout.decode("utf-8").splitlines()
        if line.startswith(IGNORED_PREFIX)
    ]


def _is_ignored(project: Path, path: str) -> bool:
    """Report whether `project`'s ignore rules match `path`, which need not exist."""
    return _git(project, "check-ignore", "-q", "--no-index", path).returncode == 0


class TestRenderedOutputIsNotSelfIgnored:
    @pytest.mark.parametrize("layer", LAYERS, ids=lambda p: p.name)
    def test_no_rendered_path_is_ignored_by_the_render(
        self, layer: Path, tmp_path: Path
    ) -> None:
        project = render(layer.name, tmp_path)
        _init_repo(project)

        assert not _self_ignored_paths(project)

    @pytest.mark.parametrize("layer", LAYERS, ids=lambda p: p.name)
    def test_the_lock_file_the_render_commits_is_not_ignored(
        self, layer: Path, tmp_path: Path
    ) -> None:
        project = render(layer.name, tmp_path)
        _init_repo(project)

        assert not _is_ignored(project, COMMITTED_LOCKFILE)

    def test_the_check_reports_a_planted_violation(self, tmp_path: Path) -> None:
        project = render(LAYERS[0].name, tmp_path)
        _init_repo(project)
        planted = project / "dist" / "artifact.txt"
        planted.parent.mkdir(parents=True)
        planted.write_text("matched by the rendered .gitignore", encoding="utf-8")

        assert _self_ignored_paths(project) == ["dist/"]
        assert _is_ignored(project, "dist/artifact.txt")
