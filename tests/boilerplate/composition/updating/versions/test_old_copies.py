"""Tests for the old-copy versions of a layer in old_copies.py."""

import pytest

from boilerplate.composition.updating.versions import old_copy_for
from tests.boilerplate.composition.updating.versions.conftest import (
    layer,
    no_version_layer,
    past_tag_layer,
    v,
)


class TestOldCopyFor:
    """The old copy renders a layer at its commit and each ancestor at the lock."""

    def test_a_layer_uses_its_own_commit_and_the_locks_ancestor_versions(self) -> None:
        core = layer("core", "1.0.0", commit="2.0.0")
        service = layer("service", "1.0.0", commit="1.1.0", ancestors=["core"])

        old = old_copy_for(service, {"core": core, "service": service})

        assert old.layer == "service"
        assert old.commit == "1.1.0"
        assert dict(old.versions) == {"core": v("1.0.0"), "service": v("1.1.0")}

    def test_an_ancestor_that_updated_ahead_does_not_move_the_descendants_base(
        self,
    ) -> None:
        """Core's own commit moved to 2.0.0; service was rendered against 1.0.0."""
        core = layer("core", "1.0.0", commit="2.0.0")
        service = layer("service", "1.0.0", ancestors=["core"])

        old = old_copy_for(service, {"core": core, "service": service})

        assert old.versions["core"] == v("1.0.0")

    def test_a_root_layer_has_only_itself(self) -> None:
        core = layer("core", "1.0.0")

        assert dict(old_copy_for(core, {"core": core}).versions) == {"core": v("1.0.0")}

    def test_keeps_the_raw_commit_string_for_the_checkout(self) -> None:
        past = past_tag_layer("core", "1.0.0", "1.0.0-2-gabc1234", "1.0.0.post2")

        assert old_copy_for(past, {"core": past}).commit == "1.0.0-2-gabc1234"

    def test_refuses_a_layer_whose_commit_yields_no_version(self) -> None:
        stray = no_version_layer("core", "1.0.0")

        with pytest.raises(ValueError, match="core"):
            old_copy_for(stray, {"core": stray})
