"""The warnings an update gives of what changed outside Boilerplate."""

import hashlib
from datetime import UTC, datetime
from importlib.metadata import version as installed_version
from pathlib import Path

from boilerplate.composition.updating.walk.answers_warnings import (
    answers_warnings,
    copier_version_warnings,
)
from boilerplate.models import BoilerplateLock, LockLayer
from boilerplate.types import SerializableVersion

STAMP = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)


def lock_of(
    *layers: str,
    hashes: dict[str, str] | None = None,
    copier_version: str | None = None,
) -> BoilerplateLock:
    """Build a lock of `layers` with the given answers-file hashes."""
    return BoilerplateLock(
        boilerplate_version="0.3.0",
        copier_version=copier_version or installed_version("copier"),
        created_at=STAMP,
        updated_at=STAMP,
        root_template=f"{layers[-1]}@1.0.0",
        copier_answers_file_hashes=hashes,
        layers=tuple(
            LockLayer(
                name=name,
                version=SerializableVersion("1.0.0"),
                source="x",
                checksum="sha256:" + "a" * 64,
            )
            for name in layers
        ),
    )


def digest(text: str) -> str:
    """Return the SHA-256 hex digest of `text` as UTF-8."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class TestAnswersWarnings:
    def test_an_unchanged_answers_file_gives_no_warning(self, tmp_path: Path) -> None:
        """Compare the file with the hash the lock holds."""
        (tmp_path / ".copier-answers.core.yml").write_bytes(b"a: 1\n")

        warnings = answers_warnings(
            tmp_path, lock_of("core", hashes={"core": digest("a: 1\n")})
        )

        assert warnings == []

    def test_an_edited_answers_file_names_the_layer(self, tmp_path: Path) -> None:
        """Use the design's wording for the layer whose file changed."""
        (tmp_path / ".copier-answers.core.yml").write_text("a: 2\n", encoding="utf-8")

        warnings = answers_warnings(
            tmp_path, lock_of("core", hashes={"core": digest("a: 1\n")})
        )

        assert warnings == [
            "Answer state for layer 'core' may have been externally modified since "
            "the last Boilerplate operation. The update will use the current "
            ".copier-answers.core.yml contents."
        ]

    def test_a_layer_the_lock_holds_no_hash_for_is_not_compared(
        self, tmp_path: Path
    ) -> None:
        """Leave a lock without hashes alone."""
        (tmp_path / ".copier-answers.core.yml").write_text("a: 2\n", encoding="utf-8")

        assert answers_warnings(tmp_path, lock_of("core")) == []


class TestCopierVersionWarnings:
    def test_the_same_copier_gives_no_warning(self) -> None:
        """Stay quiet when the lock records the installed Copier."""
        assert copier_version_warnings(lock_of("core")) == []

    def test_a_different_copier_names_both_versions(self) -> None:
        """Say which Copier last rendered the project and which runs now."""
        warnings = copier_version_warnings(lock_of("core", copier_version="9.0.0"))

        assert warnings == [
            "The project was last rendered with Copier 9.0.0; this update runs with "
            f"Copier {installed_version('copier')}."
        ]
