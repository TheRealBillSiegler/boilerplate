"""The view lookup of ``ScopedWorker``; its renders are in the integration tests."""

from pathlib import Path

import pytest

from boilerplate.composition.updating import ScopedWorker
from boilerplate.composition.views import LayerView

OLD = LayerView({"old_question": {}}, ())
NEW = LayerView({"new_question": {}}, ())


def _worker(tmp_path: Path, views: dict[str, LayerView]) -> ScopedWorker:
    return ScopedWorker(  # pyright: ignore[reportCallIssue]
        src_path=str(tmp_path), dst_path=tmp_path, views_by_ref=views
    )


class TestViewFor:
    def test_returns_the_view_keyed_by_the_ref(self, tmp_path: Path) -> None:
        worker = _worker(tmp_path, {"v1": OLD, "v2": NEW})

        assert worker.view_for("v2") == NEW

    @pytest.mark.parametrize("ref", [None, "v3"])
    def test_a_ref_with_no_view_raises_naming_the_known_refs(
        self, tmp_path: Path, ref: str | None
    ) -> None:
        worker = _worker(tmp_path, {"v1": OLD, "v2": NEW})

        with pytest.raises(KeyError, match=r"\['v1', 'v2'\]"):
            worker.view_for(ref)
