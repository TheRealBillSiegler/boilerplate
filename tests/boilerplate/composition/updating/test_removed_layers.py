"""The rule that decides which layers an update reports as removed."""
# Spec: docs/design/06-project-lifecycle.md §Step 3: Build UpdatePlan

from datetime import UTC, datetime

from boilerplate.composition.updating.removed_layers import removed_layers
from boilerplate.models import BoilerplateLock, JoinedVia, LockLayer
from boilerplate.types import SerializableVersion

STAMP = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)


def _lock(*layers: tuple[str, JoinedVia]) -> BoilerplateLock:
    """Return a lock listing `layers` in order, the first of which is the root."""
    return BoilerplateLock(
        boilerplate_version="0.3.0",
        copier_version="9.18.1",
        created_at=STAMP,
        updated_at=STAMP,
        root_template="app@1.0.0",
        layers=tuple(
            LockLayer(
                name=name,
                version=SerializableVersion("1.0.0"),
                joined_via=joined_via,
                source="x",
                checksum="sha256:" + "a" * 64,
            )
            for name, joined_via in layers
        ),
    )


class TestRemovedLayers:
    """A layer is removed if it joined through extends and the root drops it."""

    def test_a_layer_through_extends_that_the_root_no_longer_reaches_is_removed(
        self,
    ) -> None:
        lock = _lock(
            ("base", JoinedVia.EXTENDS),
            ("legacy", JoinedVia.EXTENDS),
            ("app", JoinedVia.EXTENDS),
        )

        assert removed_layers(lock, {"base", "app"}) == ("legacy",)

    def test_a_layer_added_on_purpose_stays_though_the_root_does_not_reach_it(
        self,
    ) -> None:
        """The root's target does not govern a layer `add` introduced (06)."""
        lock = _lock(
            ("base", JoinedVia.EXTENDS),
            ("app", JoinedVia.EXTENDS),
            ("docs", JoinedVia.ADD),
        )

        assert removed_layers(lock, {"base", "app"}) == ()

    def test_a_layer_the_root_still_reaches_is_kept(self) -> None:
        lock = _lock(("base", JoinedVia.EXTENDS), ("app", JoinedVia.EXTENDS))

        assert removed_layers(lock, {"base", "app"}) == ()

    def test_lists_the_removed_layers_in_the_locks_order(self) -> None:
        lock = _lock(
            ("a", JoinedVia.EXTENDS),
            ("b", JoinedVia.EXTENDS),
            ("c", JoinedVia.EXTENDS),
            ("app", JoinedVia.EXTENDS),
        )

        assert removed_layers(lock, {"app"}) == ("a", "b", "c")
