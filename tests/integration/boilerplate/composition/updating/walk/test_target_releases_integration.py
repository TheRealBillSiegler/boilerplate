"""Choosing the release of each layer against real tagged repositories."""

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from packaging.version import Version

from boilerplate.common.exceptions import TemplateNotFoundError
from boilerplate.composition.updating.release_ref import ReleaseRef
from boilerplate.composition.updating.walk.lock_releases import lock_releases
from boilerplate.composition.updating.walk.target_releases import (
    named_releases,
    recorded_releases,
)
from boilerplate.models import BoilerplateLock, LockLayer
from boilerplate.repository.release_checkouts import ReleaseCheckouts
from boilerplate.types import SerializableVersion
from tests.boilerplate.templates.conftest import build_layer_repo
from tests.integration.boilerplate.composition.temp_dir import temp_dir_inside

STAMP = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def isolated_temp(tmp_path: Path) -> Iterator[Path]:
    """Redirect temp-directory lookups under the test's `tmp_path`."""
    with temp_dir_inside(tmp_path) as scratch:
        yield scratch


@pytest.fixture
def source(tmp_path: Path) -> str:
    """Return a template repository tagged v1.0.0 and 1.1.0, the spellings mixed."""
    releases: dict[str, Path] = {}
    for tag in ("v1.0.0", "1.1.0"):
        release = tmp_path / "releases" / tag
        release.mkdir(parents=True)
        (release / "marker.txt").write_text(tag, encoding="utf-8")
        releases[tag] = release
    return build_layer_repo(tmp_path / "repo", releases).as_posix()


@pytest.fixture
def checkouts() -> Iterator[ReleaseCheckouts]:
    """Return release checkouts, removed after the test."""
    with ReleaseCheckouts() as held:
        yield held


def lock_of(source: str, commit: str | None) -> BoilerplateLock:
    """Build a lock whose one layer, ``core``, records `commit` at 1.0.0."""
    return BoilerplateLock(
        boilerplate_version="0.3.0",
        copier_version="9.18.1",
        created_at=STAMP,
        updated_at=STAMP,
        root_template="core@1.0.0",
        layers=(
            LockLayer(
                name="core",
                version=SerializableVersion("1.0.0"),
                source=source,
                commit=commit,
                checksum="sha256:" + "a" * 64,
            ),
        ),
    )


class TestLockReleases:
    def test_uses_the_commit_the_lock_records(self, source: str) -> None:
        """Check the layer out where it was rendered from."""
        releases = lock_releases(lock_of(source, "v1.0.0"), {"core": source})

        assert releases == {"core": ReleaseRef(source=source, ref="v1.0.0")}

    def test_finds_the_tag_of_the_version_when_the_lock_records_no_commit(
        self, source: str
    ) -> None:
        """Resolve version 1.0.0 to the tag the repository spells ``v1.0.0``."""
        releases = lock_releases(lock_of(source, None), {"core": source})

        assert releases["core"].ref == "v1.0.0"


class TestNamedReleases:
    def test_a_layer_with_no_ref_moves_to_its_latest_tag(
        self, source: str, checkouts: ReleaseCheckouts
    ) -> None:
        """Resolve the latest release as Copier does, keeping the tag as the ref."""
        releases, versions = named_releases({"core": source}, {"core": None}, checkouts)

        assert (releases["core"].ref, versions["core"]) == ("1.1.0", Version("1.1.0"))

    def test_a_layer_with_a_ref_moves_to_that_ref(
        self, source: str, checkouts: ReleaseCheckouts
    ) -> None:
        """Keep the ref as asked and read its version from the checkout."""
        releases, versions = named_releases(
            {"core": source}, {"core": "v1.0.0"}, checkouts
        )

        assert (releases["core"].ref, versions["core"]) == ("v1.0.0", Version("1.0.0"))

    def test_a_source_that_is_not_a_git_repository_is_refused(
        self, tmp_path: Path, checkouts: ReleaseCheckouts
    ) -> None:
        """Name the layer: a plain directory has no release to move to."""
        plain = tmp_path / "plain"
        plain.mkdir()
        (plain / "marker.txt").write_text("x", encoding="utf-8")

        with pytest.raises(TemplateNotFoundError, match="core"):
            named_releases({"core": plain.as_posix()}, {"core": None}, checkouts)


class TestRecordedReleases:
    def test_resolves_each_recorded_version_to_its_tag(self, source: str) -> None:
        """Find the ref a paused update's recorded version names."""
        releases = recorded_releases(
            {"core": source}, {"core": SerializableVersion("1.0.0")}
        )

        assert releases == {"core": ReleaseRef(source=source, ref="v1.0.0")}
