"""Tests exit code behavior and contracts for CLI operations."""

import pytest

from boilerplate.constants import ExitCode


class TestExitCodeBehavior:
    """Tests ExitCode enum provides correct shell exit semantics."""

    def test_success_indicates_normal_completion(self) -> None:
        """Success exit code indicates normal program completion."""
        assert ExitCode.SUCCESS == 0
        assert bool(ExitCode.SUCCESS) is False  # Falsy for success in shell logic

    def test_failure_codes_indicate_error_conditions(self) -> None:
        """Non-zero exit codes indicate different error conditions."""
        error_codes = [
            ExitCode.FAILURE,
            ExitCode.CONFIG_ERROR,
            ExitCode.VALIDATION_ERROR,
            ExitCode.ACTION_REQUIRED,
        ]

        for code in error_codes:
            assert code != 0, f"{code.name} should be non-zero"
            assert bool(code) is True, f"{code.name} should be truthy for shell logic"

    def test_exit_codes_are_distinct(self) -> None:
        """Each exit code has a unique value for shell distinction."""
        all_codes = list(ExitCode)
        code_values = [code.value for code in all_codes]

        assert len(code_values) == len(set(code_values)), "Exit codes must be unique"

    def test_exit_codes_support_int_operations(self) -> None:
        """Exit codes work as integers for shell compatibility."""
        # Test that they can be used in int contexts
        assert int(ExitCode.SUCCESS) == 0
        assert ExitCode.FAILURE + 0 == 1
        assert ExitCode.CONFIG_ERROR < 10  # Reasonable range for shell codes

    @pytest.mark.parametrize("exit_code", list(ExitCode))
    def test_exit_codes_have_descriptive_names(self, exit_code: ExitCode) -> None:
        """Each exit code has a meaningful name."""
        assert exit_code.name.isupper(), f"{exit_code.name} should be uppercase"
        assert "_" in exit_code.name or exit_code.name in ["SUCCESS", "FAILURE"], (
            f"{exit_code.name} should use snake_case or be a simple word"
        )

    def test_exit_code_enumeration_is_complete(self) -> None:
        """Verifies the canonical six-value set from the design is defined."""
        expected_codes = {
            "SUCCESS",
            "FAILURE",
            "CONFIG_ERROR",
            "VALIDATION_ERROR",
            "ACTION_REQUIRED",
            "USER_CANCELLED",
        }
        actual_codes = {code.name for code in ExitCode}

        assert actual_codes == expected_codes, (
            f"Missing or extra exit codes. Expected: {expected_codes}, "
            f"Actual: {actual_codes}"
        )

    def test_action_required_distinguishes_pause_from_failure(self) -> None:
        """ACTION_REQUIRED is 4, distinct from the hard-failure code 1."""
        assert ExitCode.ACTION_REQUIRED == 4
        assert ExitCode.ACTION_REQUIRED != ExitCode.FAILURE
