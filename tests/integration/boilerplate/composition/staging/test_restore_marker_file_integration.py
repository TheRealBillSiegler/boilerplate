"""The restore marker's file and ref in the project's git directory.

Design 06 §Interrupted copy back: the marker is a JSON file at
``git rev-parse --git-path boilerplate-restore.json``, paired with the ref
``refs/worktree/boilerplate/restore`` that pins the copy back's source commit.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from boilerplate.common.exceptions import UpdateInterruptedError
from boilerplate.composition.staging.restore_marker_file import (
    pin_result,
    read_marker,
    remove_marker,
    write_marker,
)
from boilerplate.models import (
    RestoreKind,
    RestoreMarker,
    RestoreOperation,
    RestorePhase,
)
from tests.boilerplate.templates.conftest import git
from tests.integration.boilerplate.composition.staging.conftest import head

REF = "refs/worktree/boilerplate/restore"


def marker_for(commit: str) -> RestoreMarker:
    return RestoreMarker(
        operation=RestoreOperation.UPDATE,
        kind=RestoreKind.COMPLETE,
        phase=RestorePhase.COPY_BACK,
        start_commit=commit,
        result_commit=commit,
        targets={"core": "1.1.0"},
        started_at=datetime(2026, 10, 9, 12, 0, tzinfo=UTC),
    )


def ref_exists(project: Path) -> bool:
    return git(project, "for-each-ref", REF).strip() != ""


class TestWriteAndRead:
    def test_reads_back_what_was_written(self, project: Path) -> None:
        """Round-trip the marker through its file."""
        marker = marker_for(head(project))

        write_marker(project, marker)

        assert read_marker(project) == marker

    def test_writes_the_file_git_names_for_it(self, project: Path) -> None:
        """Put the file where ``git rev-parse --git-path`` says, in the git dir."""
        write_marker(project, marker_for(head(project)))

        assert (project / ".git" / "boilerplate-restore.json").is_file()

    def test_leaves_the_working_tree_clean(self, project: Path) -> None:
        """Keep the marker out of the tracked tree, so it is never committed."""
        write_marker(project, marker_for(head(project)))

        assert git(project, "status", "--porcelain") == ""

    def test_reads_none_where_no_run_left_a_marker(self, project: Path) -> None:
        """Report no marker for a project no run was cut off in."""
        assert read_marker(project) is None

    def test_a_marker_that_does_not_parse_stops_naming_the_file(
        self, project: Path
    ) -> None:
        """Stop with BP_UPDATE_INTERRUPTED, as design 06 says, naming the file."""
        (project / ".git" / "boilerplate-restore.json").write_text(
            '{"operation": "upd', encoding="utf-8"
        )

        with pytest.raises(UpdateInterruptedError, match=r"boilerplate-restore\.json"):
            read_marker(project)

    def test_a_marker_that_is_not_utf8_stops_naming_the_file(
        self, project: Path
    ) -> None:
        """Stop with BP_UPDATE_INTERRUPTED on bytes that do not decode as UTF-8."""
        (project / ".git" / "boilerplate-restore.json").write_bytes(b"\xff\xfe{")

        with pytest.raises(UpdateInterruptedError, match=r"boilerplate-restore\.json"):
            read_marker(project)

    def test_the_unparseable_marker_remediation_discards_the_ref(
        self, project: Path
    ) -> None:
        """Tell the user how to discard the marker: the file and the ref."""
        (project / ".git" / "boilerplate-restore.json").write_text(
            "not json", encoding="utf-8"
        )

        with pytest.raises(UpdateInterruptedError) as stop:
            read_marker(project)

        assert f"git update-ref -d {REF}" in (stop.value.remediation or "")


class TestRef:
    def test_pin_points_the_ref_at_the_result(self, project: Path) -> None:
        """Pin the copy back's source commit with the per-worktree ref."""
        pin_result(project, head(project))

        assert git(project, "rev-parse", REF).strip() == head(project)

    def test_remove_drops_the_file_and_the_ref(self, project: Path) -> None:
        """Remove both halves of the marker."""
        pin_result(project, head(project))
        write_marker(project, marker_for(head(project)))

        remove_marker(project)

        assert (read_marker(project), ref_exists(project)) == (None, False)

    def test_remove_drops_a_ref_left_without_a_marker(self, project: Path) -> None:
        """Clear the leftover of a crash between pinning and writing the marker."""
        pin_result(project, head(project))

        remove_marker(project)

        assert not ref_exists(project)

    def test_remove_with_nothing_to_remove_is_a_no_op(self, project: Path) -> None:
        """Pass on a project that has neither file nor ref."""
        remove_marker(project)

        assert (read_marker(project), ref_exists(project)) == (None, False)
