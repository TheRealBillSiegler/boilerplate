"""The checks an update or an add makes before it reads the working tree.

Design 06 §Pre-Flight Check orders them: the project is a git repository root
with a commit, the operation lock is taken, and the restore-marker rules run
inside it.
"""

from pathlib import Path

import pytest

from boilerplate.common.exceptions import (
    ConcurrencyContentionError,
    UpdateInterruptedError,
    UpdateProjectNotReadyError,
)
from boilerplate.composition.staging.operation_lock import operation_lock
from boilerplate.composition.staging.operation_preflight import preflight
from boilerplate.composition.staging.restore_marker_file import marker_path
from boilerplate.models import RestoreOperation


def plant_unparseable_marker(project: Path) -> None:
    marker_path(project).write_text("not a marker", encoding="utf-8")


class TestPreflight:
    def test_a_folder_that_is_not_a_repository_root_stops_first(
        self, project: Path
    ) -> None:
        """Check the repository root before the lock, which lives in its git dir."""
        inner = project / "inner"
        inner.mkdir()

        with (
            pytest.raises(UpdateProjectNotReadyError),
            preflight(inner, RestoreOperation.UPDATE, timeout=0),
        ):
            pass

    def test_the_marker_rules_wait_for_the_lock(self, project: Path) -> None:
        """Read the marker only inside the lock, so a live run's marker is left be."""
        plant_unparseable_marker(project)

        with (
            operation_lock(project, timeout=0),
            pytest.raises(ConcurrencyContentionError),
            preflight(project, RestoreOperation.UPDATE, timeout=0.1),
        ):
            pass

    def test_the_marker_rules_run_inside_the_lock(self, project: Path) -> None:
        """Apply the marker rules once the lock is held."""
        plant_unparseable_marker(project)

        with (
            pytest.raises(UpdateInterruptedError),
            preflight(project, RestoreOperation.UPDATE, timeout=0),
        ):
            pass
