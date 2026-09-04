"""Unit tests for boilerplate.common.env."""

import pytest

from boilerplate.common.env import env_flag


class TestEnvFlag:
    """Truthiness rule for env-var mode flags.

    Governs ``BOILERPLATE_CI`` and ``BOILERPLATE_NON_INTERACTIVE``.
    Surrounding whitespace is trimmed first, so a whitespace-only value reads
    as unset. Enabled for any remaining non-empty value other than
    ``0``/``false`` (case-insensitive); unset, empty, ``0``, and ``false``
    all read as unset.
    """

    def test_unset_is_falsy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("BOILERPLATE_TEST_FLAG", raising=False)
        assert env_flag("BOILERPLATE_TEST_FLAG") is False

    def test_empty_string_is_falsy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BOILERPLATE_TEST_FLAG", "")
        assert env_flag("BOILERPLATE_TEST_FLAG") is False

    @pytest.mark.parametrize("value", ["   ", "\t", "\n"])
    def test_whitespace_only_is_falsy(
        self, monkeypatch: pytest.MonkeyPatch, value: str
    ) -> None:
        """Whitespace-only reads as unset once trimmed, not as truthy garbage."""
        monkeypatch.setenv("BOILERPLATE_TEST_FLAG", value)
        assert env_flag("BOILERPLATE_TEST_FLAG") is False

    @pytest.mark.parametrize(
        "value", ["0", "false", "False", "FALSE", "fAlSe", "  0", " false ", "false\n"]
    )
    def test_explicit_zero_or_false_is_falsy(
        self, monkeypatch: pytest.MonkeyPatch, value: str
    ) -> None:
        """Falsy even with surrounding whitespace, as trimming happens first."""
        monkeypatch.setenv("BOILERPLATE_TEST_FLAG", value)
        assert env_flag("BOILERPLATE_TEST_FLAG") is False

    @pytest.mark.parametrize("value", ["1", "true", "True", "yes", "on", "banana"])
    def test_any_other_value_is_truthy(
        self, monkeypatch: pytest.MonkeyPatch, value: str
    ) -> None:
        """A garbage value like 'banana' is truthy per the spec's truthiness rule."""
        monkeypatch.setenv("BOILERPLATE_TEST_FLAG", value)
        assert env_flag("BOILERPLATE_TEST_FLAG") is True
