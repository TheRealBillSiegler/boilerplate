"""Writing the lock of an update, on a locked family project."""

from pathlib import Path

import pytest

from boilerplate.composition.updating.walk.update_lock_writer import write_update_lock
from boilerplate.project_state.lock_file import read_lock
from tests.integration.boilerplate.composition.family import Family
from tests.integration.boilerplate.composition.scenarios.builders import (
    compose_locked_family,
)

pytestmark = [pytest.mark.scenario]

TAGS = {"core": "1.0.0", "service": "1.0.0"}


class TestWriteUpdateLock:
    def test_writes_the_lock_the_answers_files_describe(
        self, family: Family, tmp_path: Path
    ) -> None:
        """Replace the lock with one stamped by the running tool."""
        project = compose_locked_family(family, tmp_path, "service", TAGS)
        previous = read_lock(project)

        written = write_update_lock(project, previous, "9.9.9")

        assert read_lock(project) == written

    def test_keeps_when_the_project_was_created(
        self, family: Family, tmp_path: Path
    ) -> None:
        """Carry ``created_at`` over from the lock being replaced."""
        project = compose_locked_family(family, tmp_path, "service", TAGS)
        previous = read_lock(project)

        written = write_update_lock(project, previous, "9.9.9")

        assert written.created_at == previous.created_at

    def test_stamps_the_version_of_the_tool_writing_it(
        self, family: Family, tmp_path: Path
    ) -> None:
        """Record the tool version the caller passes."""
        project = compose_locked_family(family, tmp_path, "service", TAGS)

        written = write_update_lock(project, read_lock(project), "9.9.9")

        assert written.boilerplate_version == "9.9.9"
