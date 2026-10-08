"""Tests for the downgrade rule in downgrades.py."""

import pytest

from boilerplate.common.exceptions import UpdateDowngradeError
from boilerplate.composition.updating.versions import reject_downgrades
from tests.boilerplate.composition.updating.versions.conftest import (
    layer,
    no_version_layer,
    past_tag_layer,
    v,
)


class TestTargetsThatDoNotGoBack:
    """Equal or newer targets pass."""

    @pytest.mark.parametrize("target", ["1.0.0", "1.0.1", "2.0.0"])
    def test_passes(self, target: str) -> None:
        reject_downgrades((layer("core", "1.0.0"),), {"core": v(target)})

    def test_a_target_past_a_post_release_commit_passes(self) -> None:
        past = past_tag_layer("core", "1.1.0", "1.1.0-2-gabc", "1.1.0.post2")

        reject_downgrades((past,), {"core": v("1.2.0")})


class TestADowngrade:
    """A target older than the recorded version stops before any layer runs."""

    def test_names_the_layer_its_recorded_version_and_the_target(self) -> None:
        with pytest.raises(UpdateDowngradeError) as caught:
            reject_downgrades(
                (layer("core", "2.0.0"), layer("service", "1.1.0")),
                {"core": v("2.0.0"), "service": v("1.0.0")},
            )

        assert (caught.value.layer, caught.value.recorded, caught.value.target) == (
            "service",
            "1.1.0",
            "1.0.0",
        )
        message = str(caught.value)
        assert "service" in message
        assert "1.1.0" in message
        assert "1.0.0" in message

    def test_the_recorded_version_is_the_commit_not_the_lock(self) -> None:
        """Core's own commit is ahead of the lock; going to the lock is back."""
        ahead = layer("core", "1.0.0", commit="2.0.0")

        with pytest.raises(UpdateDowngradeError):
            reject_downgrades((ahead,), {"core": v("1.0.0")})

    def test_a_tag_older_than_a_post_release_of_it_is_a_downgrade(self) -> None:
        past = past_tag_layer("core", "1.1.0", "1.1.0-2-gabc", "1.1.0.post2")

        with pytest.raises(UpdateDowngradeError):
            reject_downgrades((past,), {"core": v("1.1.0")})


class TestACommitWithNoVersion:
    """A recorded commit that yields no version stops the update too."""

    def test_stops_naming_the_layer_and_the_commit(self) -> None:
        stray = no_version_layer("core", "1.0.0", commit="deadbeef")

        with pytest.raises(UpdateDowngradeError, match="deadbeef") as caught:
            reject_downgrades((stray,), {"core": v("2.0.0")})

        assert caught.value.layer == "core"
        assert caught.value.recorded == ""


class TestATargetMissing:
    """Every layer to run needs a target."""

    def test_raises_a_value_error(self) -> None:
        with pytest.raises(ValueError, match="core"):
            reject_downgrades((layer("core", "1.0.0"),), {})
