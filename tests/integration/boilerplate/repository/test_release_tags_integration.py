"""``release_tag_for_version`` against a real tagged git repository."""

from pathlib import Path

import pytest
from packaging.version import Version

from boilerplate.common.exceptions import TemplateNotFoundError
from boilerplate.repository.release_tags import release_tag_for_version
from tests.boilerplate.templates.conftest import build_layer_repo


@pytest.fixture
def source(tmp_path: Path) -> str:
    """Return a template repository tagged v1.0.0 and 1.1.0, the spellings mixed."""
    releases: dict[str, Path] = {}
    for tag in ("v1.0.0", "1.1.0"):
        release = tmp_path / "releases" / tag
        release.mkdir(parents=True)
        (release / "marker.txt").write_text(f"release {tag}\n", encoding="utf-8")
        releases[tag] = release
    return build_layer_repo(tmp_path / "repo", releases).as_posix()


class TestReleaseTagForVersion:
    @pytest.mark.parametrize(
        ("version", "tag"), [("1.0.0", "v1.0.0"), ("1.1.0", "1.1.0")]
    )
    def test_finds_the_tag_that_names_the_version(
        self, source: str, version: str, tag: str
    ) -> None:
        """Return the tag as spelled in the repository."""
        assert release_tag_for_version(source, Version(version)) == tag

    def test_a_version_no_tag_names_is_not_found(self, source: str) -> None:
        """Name the source and the version in the error."""
        with pytest.raises(TemplateNotFoundError, match=r"2\.0\.0"):
            release_tag_for_version(source, Version("2.0.0"))
