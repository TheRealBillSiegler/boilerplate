"""Tests for the atomic text write in atomic_write.py."""

from pathlib import Path

import pytest

from boilerplate.project_state.atomic_write import write_text_atomically


class TestWriteTextAtomically:
    """A write leaves the whole new file or the whole old one, never a part."""

    def test_creates_the_file(self, tmp_path: Path) -> None:
        target = tmp_path / "state.yml"

        write_text_atomically(target, "a: 1\n")

        assert target.read_text(encoding="utf-8") == "a: 1\n"

    def test_creates_missing_parent_directories(self, tmp_path: Path) -> None:
        target = tmp_path / ".boilerplate" / "state.yml"

        write_text_atomically(target, "a: 1\n")

        assert target.read_text(encoding="utf-8") == "a: 1\n"

    def test_replaces_an_existing_file(self, tmp_path: Path) -> None:
        target = tmp_path / "state.yml"
        target.write_text("old\n", encoding="utf-8")

        write_text_atomically(target, "new\n")

        assert target.read_text(encoding="utf-8") == "new\n"

    def test_writes_lf_line_endings_on_every_platform(self, tmp_path: Path) -> None:
        target = tmp_path / "state.yml"

        write_text_atomically(target, "a: 1\nb: 2\n")

        assert target.read_bytes() == b"a: 1\nb: 2\n"

    def test_leaves_no_temporary_file_behind(self, tmp_path: Path) -> None:
        write_text_atomically(tmp_path / "state.yml", "a: 1\n")

        assert [p.name for p in tmp_path.iterdir()] == ["state.yml"]

    def test_a_failed_rename_keeps_the_old_file_and_removes_the_temporary(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = tmp_path / "state.yml"
        target.write_text("old\n", encoding="utf-8")

        def refuse(_self: Path, _target: Path) -> Path:
            raise OSError("rename refused")

        monkeypatch.setattr(Path, "replace", refuse)

        with pytest.raises(OSError, match="rename refused"):
            write_text_atomically(target, "new\n")

        assert target.read_text(encoding="utf-8") == "old\n"
        assert [p.name for p in tmp_path.iterdir()] == ["state.yml"]
