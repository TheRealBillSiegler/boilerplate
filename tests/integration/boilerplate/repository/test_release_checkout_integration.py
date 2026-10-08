"""``checked_out_release`` against a real tagged git repository."""

from pathlib import Path

import pytest
from packaging.version import Version

from boilerplate.repository.release_checkout import checked_out_release
from tests.boilerplate.templates.conftest import build_layer_repo, commit_all, git


@pytest.fixture
def source(tmp_path: Path) -> Path:
    """Return a template repository tagged 1.0.0 and 1.1.0, then one commit past it."""
    releases: dict[str, Path] = {}
    for tag in ("1.0.0", "1.1.0"):
        release = tmp_path / "releases" / tag
        release.mkdir(parents=True)
        (release / "marker.txt").write_text(f"release {tag}\n", encoding="utf-8")
        releases[tag] = release
    repo = build_layer_repo(tmp_path / "repo", releases)
    (repo / "marker.txt").write_text("past the tag\n", encoding="utf-8")
    commit_all(repo, "work after 1.1.0")
    return repo


def marker(path: Path) -> str:
    """Return the first line of the checkout's marker file."""
    return (path / "marker.txt").read_text(encoding="utf-8").strip()


class TestCheckedOutRelease:
    def test_checks_out_the_named_tag(self, source: Path) -> None:
        """Hand back the tag's content, its description and its version."""
        with checked_out_release(source.as_posix(), "1.0.0") as release:
            seen = (marker(release.path), release.commit, release.version)

        assert seen == ("release 1.0.0", "1.0.0", Version("1.0.0"))

    def test_without_a_ref_checks_out_the_latest_tag(self, source: Path) -> None:
        """Resolve the latest release as Copier does, not the branch tip."""
        with checked_out_release(source.as_posix(), None) as release:
            seen = (marker(release.path), release.commit, release.version)

        assert seen == ("release 1.1.0", "1.1.0", Version("1.1.0"))

    def test_checks_out_a_describe_past_a_tag(self, source: Path) -> None:
        """Resolve ``<tag>-<n>-g<hash>``, the form Copier records in ``_commit``."""
        described = git(source, "describe", "--tags", "--always").strip()
        assert described.startswith("1.1.0-1-g")

        with checked_out_release(source.as_posix(), described) as release:
            version = release.version
            seen = (marker(release.path), release.commit)

        assert seen == ("past the tag", described)
        assert version is not None
        assert (version.base_version, version.post, version > Version("1.1.0")) == (
            "1.1.0",
            1,
            True,
        )

    def test_removes_the_clone_on_exit(self, source: Path) -> None:
        """Run Copier's cleanup so the temporary clone does not outlive the block."""
        with checked_out_release(source.as_posix(), "1.0.0") as release:
            path = release.path
            assert path.is_dir()

        assert not path.exists()

    def test_removes_the_clone_when_the_block_raises(self, source: Path) -> None:
        """Clean up on the way out of a failure too."""
        with (
            pytest.raises(RuntimeError),
            checked_out_release(source.as_posix(), "1.0.0") as release,
        ):
            path = release.path
            raise RuntimeError("boom")

        assert not path.exists()
