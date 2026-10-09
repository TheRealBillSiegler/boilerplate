"""Unit tests for `MergedTemplate`'s version reporting.

Seam: `MergedTemplate.version`, which Copier reads to choose migrations and to
print its "Copying from template version" line.
Source of truth: PEP 440 for what counts as a version.
Breaks if the fallback stops being parsed, or a value that is not a version
escapes as an exception instead of "no version". A fallback string is only a
`str` in the type system, so nothing else guarantees it parses. The rule that
a git-derived version wins over the fallback needs a tagged repository, so
`TestCopierVersionLine` in `test_engine_integration.py` pins it, together
with the progress line itself.
"""

from pathlib import Path

import pytest
from packaging.version import Version

from boilerplate.composition.rendering.models.merged_template import MergedTemplate


@pytest.fixture
def plain_folder(tmp_path: Path) -> Path:
    """Return a template directory that is not a git repository."""
    folder = tmp_path / "template"
    folder.mkdir()
    (folder / "copier.yml").write_text("{}", encoding="utf-8")
    return folder


class TestVersionOfAPlainFolder:
    def test_fallback_is_parsed_as_the_version(self, plain_folder: Path) -> None:
        template = MergedTemplate(
            url=str(plain_folder), merged_questions={}, fallback_version="1.2.3"
        )

        assert template.version == Version("1.2.3")

    def test_no_fallback_leaves_no_version(self, plain_folder: Path) -> None:
        template = MergedTemplate(url=str(plain_folder), merged_questions={})

        assert template.version is None

    @pytest.mark.parametrize("fallback", ["not-a-version", "1.2.x", ""])
    def test_fallback_that_is_not_pep_440_leaves_no_version(
        self, plain_folder: Path, fallback: str
    ) -> None:
        template = MergedTemplate(
            url=str(plain_folder), merged_questions={}, fallback_version=fallback
        )

        assert template.version is None
