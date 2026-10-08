"""Which render of Copier's update a destination directory belongs to."""

from pathlib import Path

import pytest

from boilerplate.composition.updating import RenderRole, render_role
from boilerplate.integrations.copier_types import (
    NEW_COPY_DIR_PREFIX,
    OLD_COPY_DIR_PREFIX,
)


class TestRenderRole:
    """The temp directory Copier renders a copy into names the copy."""

    @pytest.mark.parametrize(
        ("prefix", "role"),
        [
            (OLD_COPY_DIR_PREFIX, RenderRole.OLD_COPY),
            (NEW_COPY_DIR_PREFIX, RenderRole.NEW_COPY),
        ],
    )
    def test_a_copy_directory_names_its_copy(
        self, tmp_path: Path, prefix: str, role: RenderRole
    ) -> None:
        assert render_role(tmp_path / f"{prefix}x1y2") == role

    def test_a_subproject_below_a_copy_directory_is_still_that_copy(
        self, tmp_path: Path
    ) -> None:
        """Copier appends the subproject's subdirectory to the copy directory."""
        destination = tmp_path / f"{OLD_COPY_DIR_PREFIX}x1y2" / "apps" / "web"

        assert render_role(destination) == RenderRole.OLD_COPY

    def test_the_project_itself_is_the_in_place_render(self, tmp_path: Path) -> None:
        assert render_role(tmp_path / "project") == RenderRole.IN_PLACE

    def test_a_name_that_merely_mentions_a_copy_is_in_place(
        self, tmp_path: Path
    ) -> None:
        """Match the prefix, not the words."""
        assert render_role(tmp_path / "my.old_copy.notes") == RenderRole.IN_PLACE
