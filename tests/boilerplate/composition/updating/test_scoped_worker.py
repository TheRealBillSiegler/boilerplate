"""The view choice of ``ScopedWorker``; its renders are in the integration tests."""

from pathlib import Path

import pytest

from boilerplate.composition.updating import ScopedWorker
from boilerplate.composition.views import LayerView
from boilerplate.integrations.copier_types import (
    NEW_COPY_DIR_PREFIX,
    OLD_COPY_DIR_PREFIX,
)

OLD = LayerView({"old_question": {}}, ())
TARGET = LayerView({"new_question": {}}, ())


def _worker(tmp_path: Path, destination: Path) -> ScopedWorker:
    return ScopedWorker(  # pyright: ignore[reportCallIssue]
        src_path=str(tmp_path),
        dst_path=destination,
        old_view=OLD,
        target_view=TARGET,
    )


class TestViewForRender:
    def test_the_old_copy_renders_under_the_old_view(self, tmp_path: Path) -> None:
        worker = _worker(tmp_path, tmp_path / f"{OLD_COPY_DIR_PREFIX}ab12")

        assert worker.view_for_render() == OLD

    @pytest.mark.parametrize(
        "destination",
        ["project", f"{NEW_COPY_DIR_PREFIX}ab12"],
        ids=["in_place", "new_copy"],
    )
    def test_the_other_renders_use_the_target_view(
        self, tmp_path: Path, destination: str
    ) -> None:
        worker = _worker(tmp_path, tmp_path / destination)

        assert worker.view_for_render() == TARGET
