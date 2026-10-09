"""The ancestor check refuses a layer whose ancestors the project cannot supply.

The expected messages and remedies are the ones design 05 §add gives for the two
preconditions.
"""

from collections.abc import Mapping, Sequence

import pytest
from packaging.version import Version

from boilerplate.common.exceptions import (
    AddAncestorsMissingError,
    AddAncestorVersionError,
    InvalidTemplateSpecifierError,
)
from boilerplate.composition.adding.ancestor_check import check_ancestors

RECORDED = {"core": Version("1.0.0"), "service": Version("1.2.0")}
EXTENDS: Mapping[str, Sequence[str]] = {"core": [], "service": ["core"]}


def extends_of(layer: str) -> Sequence[str]:
    """Return the references `layer` extends, as the project's copy declares."""
    return EXTENDS[layer]


class TestAccepted:
    def test_ancestors_in_the_lock_pass(self) -> None:
        """Pass when every ancestor is in the lock (05 §add, ancestors precondition)."""
        check_ancestors("docs", ["core"], RECORDED, extends_of)

    def test_a_pinned_reference_at_the_recorded_version_passes(self) -> None:
        """Pass a pin equal to the recorded version (05 §add, version precondition)."""
        check_ancestors("docs", ["core@1.0.0"], RECORDED, extends_of)

    def test_a_layer_without_ancestors_passes(self) -> None:
        """Pass a layer that extends nothing (05 §add checks only ancestors)."""
        check_ancestors("standalone", [], RECORDED, extends_of)


class TestMissingAncestors:
    def test_names_each_missing_layer_and_the_remedy(self) -> None:
        """Name each missing layer and the remedy (05 §add, ancestors error)."""
        with pytest.raises(AddAncestorsMissingError) as stop:
            check_ancestors("app", ["docs", "ci"], RECORDED, extends_of)

        assert stop.value.layers == ("docs", "ci")
        assert stop.value.remediation == (
            "Run 'boilerplate add docs' and 'boilerplate add ci' first."
        )

    def test_a_missing_layer_is_named_once(self) -> None:
        """Name a missing layer once, however often it is referenced (05 §add)."""
        with pytest.raises(AddAncestorsMissingError) as stop:
            check_ancestors("app", ["docs", "docs@1.0.0"], RECORDED, extends_of)

        assert stop.value.layers == ("docs",)

    def test_an_ancestor_of_a_locked_layer_must_be_locked_too(self) -> None:
        """Follow the lock's own extends: service needs core, which is absent."""
        with pytest.raises(AddAncestorsMissingError) as stop:
            check_ancestors(
                "app",
                ["service"],
                {"service": Version("1.2.0")},
                extends_of,
            )

        assert stop.value.layers == ("core",)

    def test_missing_layers_are_reported_before_a_version_mismatch(self) -> None:
        """Report missing ancestors first (05 §add lists that check first)."""
        with pytest.raises(AddAncestorsMissingError):
            check_ancestors("app", ["core@9.9.9", "docs"], RECORDED, extends_of)


class TestAncestorVersion:
    def test_names_the_ancestor_its_version_and_the_constraint(self) -> None:
        """Name ancestor, version, constraint and remedy (05 §add, version error)."""
        with pytest.raises(AddAncestorVersionError) as stop:
            check_ancestors("docs", ["core@2.0.0"], RECORDED, extends_of)

        assert (
            stop.value.ancestor,
            stop.value.recorded,
            stop.value.constraint,
            stop.value.remediation,
        ) == ("core", "1.0.0", "core@2.0.0", "Run 'boilerplate update' first.")

    def test_the_message_carries_all_three(self) -> None:
        """Put ancestor, version and constraint in the message (05 §add)."""
        with pytest.raises(AddAncestorVersionError) as stop:
            check_ancestors("docs", ["core@2.0.0"], RECORDED, extends_of)

        message = str(stop.value)
        assert "core" in message
        assert "1.0.0" in message
        assert "core@2.0.0" in message


class TestMalformedPin:
    def test_a_pin_that_is_not_a_version_is_an_invalid_specifier(self) -> None:
        """Reject a pin that is no version as an invalid specifier (05 exit code 3)."""
        with pytest.raises(InvalidTemplateSpecifierError):
            check_ancestors("docs", ["core@latest"], RECORDED, extends_of)
