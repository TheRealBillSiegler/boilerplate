"""``ReleaseCheckouts`` against a real tagged git repository."""

from pathlib import Path

import pytest
from packaging.version import Version

from boilerplate.repository.release_checkouts import ReleaseCheckouts
from tests.boilerplate.templates.conftest import build_layer_repo


@pytest.fixture
def source(tmp_path: Path) -> str:
    """Return a template repository tagged 1.0.0 and 1.1.0."""
    releases: dict[str, Path] = {}
    for tag in ("1.0.0", "1.1.0"):
        release = tmp_path / "releases" / tag
        release.mkdir(parents=True)
        (release / "marker.txt").write_text(f"release {tag}\n", encoding="utf-8")
        releases[tag] = release
    return build_layer_repo(tmp_path / "repo", releases).as_posix()


class TestReleaseCheckouts:
    def test_hands_out_the_checkout_of_a_ref(self, source: str) -> None:
        """Check the ref out and describe it."""
        with ReleaseCheckouts() as checkouts:
            release = checkouts.get(source, "1.0.0")

            assert (
                (release.path / "marker.txt").read_text(encoding="utf-8").strip(),
                release.version,
            ) == ("release 1.0.0", Version("1.0.0"))

    def test_clones_a_source_at_a_ref_once(self, source: str) -> None:
        """Hand the same checkout back for the same source and ref."""
        with ReleaseCheckouts() as checkouts:
            first = checkouts.get(source, "1.0.0")
            second = checkouts.get(source, "1.0.0")

            assert first is second

    def test_the_latest_release_is_the_checkout_of_its_tag(self, source: str) -> None:
        """Share the clone between the latest release and its tag."""
        with ReleaseCheckouts() as checkouts:
            latest = checkouts.get(source, None)
            by_tag = checkouts.get(source, "1.1.0")

            assert (latest.commit, latest is by_tag) == ("1.1.0", True)

    def test_removes_every_clone_on_exit(self, source: str) -> None:
        """Run Copier's cleanup for each checkout the block made."""
        with ReleaseCheckouts() as checkouts:
            paths = [checkouts.get(source, tag).path for tag in ("1.0.0", "1.1.0")]
            assert all(path.is_dir() for path in paths)

        assert not any(path.exists() for path in paths)

    def test_removes_every_clone_when_the_block_raises(self, source: str) -> None:
        """Clean up on the way out of a failure too."""
        with pytest.raises(RuntimeError), ReleaseCheckouts() as checkouts:
            path = checkouts.get(source, "1.0.0").path
            raise RuntimeError("boom")

        assert not path.exists()
