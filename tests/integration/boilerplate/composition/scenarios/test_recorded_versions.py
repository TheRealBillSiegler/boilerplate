"""A recorded ``_commit`` read as a version the way Copier reads it, on real tags.

``_commit`` is the ``git describe`` string Copier records in an answers file: a
bare tag at a release, ``<tag>-<n>-g<hash>`` past one. These tests build the
description from real repositories of the template family instead of asserting
what a string should parse to.
"""

import shutil
from pathlib import Path

import pytest
from packaging.version import Version
from plumbum.commands.processes import ProcessExecutionError

from boilerplate.repository.release_checkouts import ReleaseCheckouts
from tests.boilerplate.templates.conftest import commit_all, git
from tests.integration.boilerplate.composition.family import Family

pytestmark = pytest.mark.scenario


def _describe(repo: Path) -> str:
    return git(repo, "describe", "--tags", "--always").strip()


def _version_of(source: str, commit: str) -> Version | None:
    """Return `commit` of `source` read as a version, through a checkout."""
    with ReleaseCheckouts() as checkouts:
        return checkouts.get(source, commit).version


@pytest.fixture()
def core_repo(family: Family, tmp_path: Path) -> Path:
    """Return a private copy of the family's core repository."""
    copy = tmp_path / "core"
    shutil.copytree(family.repos["core"], copy)
    return copy


class TestARecordedTag:
    """A commit that is exactly a release tag reads as that release."""

    @pytest.mark.parametrize("tag", ["1.0.0", "1.1.0", "2.0.0"])
    def test_reads_the_tag_as_its_version(self, core_repo: Path, tag: str) -> None:
        assert _version_of(str(core_repo), tag) == Version(tag)

    def test_agrees_with_the_commit_copier_records_for_that_tag(
        self, core_repo: Path
    ) -> None:
        git(core_repo, "checkout", "-q", "1.1.0")

        assert _version_of(str(core_repo), _describe(core_repo)) == Version("1.1.0")


class TestACommitPastATag:
    """A ``git describe`` string past a tag reads as a post-release of it."""

    def test_reads_past_a_plain_tag(self, core_repo: Path) -> None:
        git(core_repo, "checkout", "-q", "1.1.0")
        (core_repo / "extra.txt").write_text("1\n", encoding="utf-8")
        commit_all(core_repo, "one past")
        (core_repo / "extra.txt").write_text("2\n", encoding="utf-8")
        commit_all(core_repo, "two past")
        described = _describe(core_repo)
        assert described.startswith("1.1.0-2-g")

        version = _version_of(str(core_repo), described)

        assert version is not None
        assert version.base_version == "1.1.0"
        assert version.post == 2
        assert Version("1.1.0") < version < Version("1.2.0")

    def test_reads_past_a_v_prefixed_tag(self, core_repo: Path) -> None:
        git(core_repo, "checkout", "-q", "2.0.0")
        (core_repo / "extra.txt").write_text("0\n", encoding="utf-8")
        commit_all(core_repo, "the v release", tag="v2.5.0")
        (core_repo / "extra.txt").write_text("1\n", encoding="utf-8")
        commit_all(core_repo, "past the v tag")
        described = _describe(core_repo)
        assert described.startswith("v2.5.0-1-g")

        version = _version_of(str(core_repo), described)

        assert version is not None
        assert version.base_version == "2.5.0"
        assert version.post == 1


class TestACommitThatIsNotAVersion:
    """A source without a readable version gives None; a missing ref is an error."""

    def test_a_directory_that_is_not_a_git_repository_has_no_version(
        self, family: Family, tmp_path: Path
    ) -> None:
        plain = tmp_path / "plain"
        shutil.copytree(family.releases["core"]["1.0.0"], plain)

        assert _version_of(str(plain), "1.0.0") is None

    def test_a_ref_the_repository_lacks_raises_instead_of_reading_as_none(
        self, core_repo: Path
    ) -> None:
        with pytest.raises(ProcessExecutionError):
            _version_of(str(core_repo), "9.9.9")
