"""``Updater``'s own contract on a locked service project of the made-up family.

The full walks, with their pauses, resumes and failed tasks, are scenarios in
``scenarios/test_update_walk.py``; these tests pin what the component promises
its callers: how a pause is reported and what the lock says about the tool.
"""

from pathlib import Path

import pytest

from boilerplate.common.exceptions import ActionRequiredError
from boilerplate.composition.updating.update_request import UpdateRequest
from boilerplate.composition.updating.update_status import UpdateStatus
from boilerplate.composition.updating.updater import Updater
from boilerplate.project_state.lock_file import read_lock
from tests.integration.boilerplate.composition.family import Family
from tests.integration.boilerplate.composition.scenarios.builders import (
    add_user_line,
    compose_locked_family,
)

pytestmark = [pytest.mark.scenario]

BEFORE = {"core": "1.0.0", "service": "1.0.0"}
LATEST = UpdateRequest(targets={"core": "2.0.0", "service": "1.2.0"})


class TestRunReportsAPause:
    def test_a_conflict_is_an_outcome_naming_the_layer_and_the_files(
        self, family: Family, tmp_path: Path
    ) -> None:
        """Return the pause for a caller that renders it, instead of raising it."""
        project = compose_locked_family(family, tmp_path, "service", BEFORE)
        add_user_line(project / "SERVICE.md")

        outcome = Updater().run(project, LATEST)

        assert (outcome.status, outcome.paused_at, outcome.conflicts) == (
            UpdateStatus.PAUSED,
            "service",
            ("SERVICE.md",),
        )

    def test_update_raises_the_same_pause(self, family: Family, tmp_path: Path) -> None:
        """Raise ``ActionRequiredError``, the exit-4 pause, from ``update``."""
        project = compose_locked_family(family, tmp_path, "service", BEFORE)
        add_user_line(project / "SERVICE.md")

        with pytest.raises(ActionRequiredError):
            Updater().update(project, LATEST)


class TestLock:
    def test_the_lock_names_the_version_of_the_tool_given(
        self, family: Family, tmp_path: Path
    ) -> None:
        """Stamp the lock the update writes with the tool version it was built with."""
        project = compose_locked_family(family, tmp_path, "service", BEFORE)

        Updater(boilerplate_version="9.9.9").update(project, LATEST)

        assert read_lock(project).boilerplate_version == "9.9.9"
