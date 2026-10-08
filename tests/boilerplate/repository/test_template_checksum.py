"""Unit tests for ``template_checksum``."""

import hashlib
from pathlib import Path

import pytest

from boilerplate.repository.template_checksum import template_checksum


def write(root: Path, files: dict[str, bytes]) -> Path:
    """Write `files` under `root` and return it."""
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return root


def digest(*parts: bytes) -> str:
    """Return the prefixed SHA-256 of the parts joined."""
    return "sha256:" + hashlib.sha256(b"".join(parts)).hexdigest()


class TestTemplateChecksum:
    def test_hashes_each_path_and_its_content_in_path_order(
        self, tmp_path: Path
    ) -> None:
        """Concatenate path then content, files sorted by forward-slash path."""
        folder = write(tmp_path, {"b.txt": b"two", "a/z.txt": b"one"})

        assert template_checksum(folder) == digest(b"a/z.txt", b"one", b"b.txt", b"two")

    def test_does_not_depend_on_the_folder_it_is_read_from(
        self, tmp_path: Path
    ) -> None:
        """Hash relative paths, so a clone anywhere has the release's checksum."""
        files = {"copier.yml": b"x: 1\n", "sub/f.txt": b"f\n"}

        first = template_checksum(write(tmp_path / "one", files))
        second = template_checksum(write(tmp_path / "two" / "deeper", files))

        assert first == second

    @pytest.mark.parametrize(
        "excluded",
        [
            ".git/HEAD",
            "pkg/__pycache__/m.pyc",
            ".mypy_cache/x",
            ".pytest_cache/x",
            ".ruff_cache/x",
            "node_modules/pkg/index.js",
        ],
    )
    def test_leaves_out_caches_and_git_history(
        self, tmp_path: Path, excluded: str
    ) -> None:
        """Skip the paths the lock schema excludes, wherever they sit."""
        kept = {"copier.yml": b"x: 1\n"}
        plain = template_checksum(write(tmp_path / "plain", kept))

        noisy = template_checksum(write(tmp_path / "noisy", {**kept, excluded: b"!"}))

        assert noisy == plain

    def test_a_changed_byte_changes_the_checksum(self, tmp_path: Path) -> None:
        """Detect an edit to a template file."""
        before = template_checksum(write(tmp_path / "a", {"f.txt": b"one\n"}))

        after = template_checksum(write(tmp_path / "b", {"f.txt": b"two\n"}))

        assert before != after

    def test_text_hashes_the_same_with_either_line_ending(self, tmp_path: Path) -> None:
        """Compare in git's content sense: a CRLF checkout equals an LF one."""
        lf = template_checksum(write(tmp_path / "lf", {"f.txt": b"a\nb\n"}))

        crlf = template_checksum(write(tmp_path / "crlf", {"f.txt": b"a\r\nb\r\n"}))

        assert lf == crlf

    def test_binary_content_is_hashed_as_it_is(self, tmp_path: Path) -> None:
        """Leave a file with a NUL byte alone: git does not convert binaries."""
        binary = b"\x00a\r\nb"

        folder = write(tmp_path, {"data.bin": binary})

        assert template_checksum(folder) == digest(b"data.bin", binary)
