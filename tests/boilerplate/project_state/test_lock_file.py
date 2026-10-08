"""Tests for reading and writing ``boilerplate.lock`` in lock_file.py."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from boilerplate.common.exceptions import (
    LockReadFailedError,
    LockSchemaUnsupportedError,
)
from boilerplate.models import BoilerplateLock, LockLayer
from boilerplate.project_state.lock_file import LOCK_FILE_NAME, read_lock, write_lock
from boilerplate.types import SerializableVersion

STAMP = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
CHECKSUM = "sha256:" + "a" * 64


def _lock() -> BoilerplateLock:
    return BoilerplateLock(
        boilerplate_version="0.3.0",
        copier_version="9.18.1",
        created_at=STAMP,
        updated_at=STAMP,
        root_template="service@1.0.0",
        copier_answers_file_hashes={"service": "b" * 64, "core": "c" * 64},
        layers=(
            LockLayer(
                name="core",
                version=SerializableVersion("1.0.0"),
                source="https://example.com/core.git",
                commit="abc",
                checksum=CHECKSUM,
            ),
            LockLayer(
                name="service",
                version=SerializableVersion("1.0.0"),
                source="https://example.com/service.git",
                commit="def",
                checksum=CHECKSUM,
            ),
        ),
    )


def _write_raw(project: Path, text: str) -> None:
    (project / LOCK_FILE_NAME).write_text(text, encoding="utf-8")


class TestWriteLock:
    """The lock is written whole, in a stable order."""

    def test_round_trips(self, tmp_path: Path) -> None:
        write_lock(tmp_path, _lock())

        assert read_lock(tmp_path) == _lock()

    def test_writes_the_file_at_the_project_root(self, tmp_path: Path) -> None:
        write_lock(tmp_path, _lock())

        assert (tmp_path / "boilerplate.lock").is_file()

    def test_sorts_keys_so_diffs_stay_clean(self, tmp_path: Path) -> None:
        write_lock(tmp_path, _lock())

        text = (tmp_path / LOCK_FILE_NAME).read_text(encoding="utf-8")
        top_level = [
            line.split(":")[0] for line in text.splitlines() if line[0].isalpha()
        ]
        assert top_level == sorted(top_level)

    def test_keeps_the_layers_in_execution_order(self, tmp_path: Path) -> None:
        write_lock(tmp_path, _lock())

        raw = yaml.safe_load((tmp_path / LOCK_FILE_NAME).read_text(encoding="utf-8"))
        assert [layer["name"] for layer in raw["layers"]] == ["core", "service"]

    def test_is_deterministic(self, tmp_path: Path) -> None:
        write_lock(tmp_path, _lock())
        first = (tmp_path / LOCK_FILE_NAME).read_bytes()

        write_lock(tmp_path, _lock())

        assert (tmp_path / LOCK_FILE_NAME).read_bytes() == first


class TestReadLock:
    """A lock that cannot be trusted fails closed with a named error."""

    def test_a_missing_file_is_a_read_failure(self, tmp_path: Path) -> None:
        with pytest.raises(LockReadFailedError, match=r"boilerplate\.lock"):
            read_lock(tmp_path)

    @pytest.mark.parametrize("text", ["a: [unclosed\n", "- just\n- a list\n", ""])
    def test_unparseable_or_non_mapping_yaml_is_a_read_failure(
        self, tmp_path: Path, text: str
    ) -> None:
        _write_raw(tmp_path, text)

        with pytest.raises(LockReadFailedError):
            read_lock(tmp_path)

    def test_a_body_that_breaks_the_schema_is_a_read_failure(
        self, tmp_path: Path
    ) -> None:
        _write_raw(tmp_path, "schema_version: boilerplate/lock@1\nlayers: nope\n")

        with pytest.raises(LockReadFailedError):
            read_lock(tmp_path)

    @pytest.mark.parametrize(
        "schema",
        [
            "",
            "1",
            "boilerplate/environment@1",
            "boilerplate/lock@x",
            "boilerplate/lock@0",
        ],
    )
    def test_an_unrecognized_schema_identifier_is_a_read_failure(
        self, tmp_path: Path, schema: str
    ) -> None:
        _write_raw(tmp_path, f"schema_version: '{schema}'\n")

        with pytest.raises(LockReadFailedError, match="schema"):
            read_lock(tmp_path)

    @pytest.mark.parametrize("schema", ["boilerplate/lock@2", "boilerplate/lock@10.1"])
    def test_a_newer_major_is_refused_before_any_other_field_is_read(
        self, tmp_path: Path, schema: str
    ) -> None:
        _write_raw(tmp_path, f"schema_version: {schema}\nlayers: {{shape: changed}}\n")

        with pytest.raises(LockSchemaUnsupportedError) as caught:
            read_lock(tmp_path)

        assert caught.value.error_code == "BP_LOCK_SCHEMA_UNSUPPORTED"

    def test_reads_a_later_minor_of_the_supported_major(self, tmp_path: Path) -> None:
        write_lock(tmp_path, _lock())
        path = tmp_path / LOCK_FILE_NAME
        text = path.read_text(encoding="utf-8").replace(
            "boilerplate/lock@1", "boilerplate/lock@1.3"
        )
        path.write_text(text + "added_later: true\n", encoding="utf-8")

        assert read_lock(tmp_path).layers == _lock().layers
