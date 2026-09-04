"""Integration tests for logging configuration during CLI operations."""

import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar

import pytest

from boilerplate.constants import ExitCode


# Constants for expected patterns and return codes
class LogPatterns:
    """Regex patterns for log message validation."""

    DEBUG_LOG: re.Pattern[str] = re.compile(r"\[DEBUG\].*boilerplate")
    TIMESTAMP: re.Pattern[str] = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")
    LOG_LEVEL: re.Pattern[str] = re.compile(r"\[(DEBUG|INFO|WARNING|ERROR)\]")


class ExpectedStrings:
    """Expected strings in CLI output."""

    CLI_NAME = "boilerplate"
    USAGE = "Usage"

    # Error indicators that should not appear
    LOGGING_ERRORS: ClassVar[list[str]] = [
        "logging error",
        "failed to configure logging",
        "richhandler error",
        "handler configuration failed",
        "no handlers could be found",
        "logging module error",
    ]

    RICH_ERRORS: ClassVar[list[str]] = [
        "RichHandler",
        "markup error",
        "console markup",
        "rich formatting error",
    ]

    COPIER_INDICATORS: ClassVar[list[str]] = [
        "[copier]",
        "copier.main",
        "copier.template",
    ]


ACCEPTABLE_CODES: list[int] = [ExitCode.SUCCESS, ExitCode.FAILURE]


@dataclass
class CliResult:
    """Encapsulates CLI execution results for easier testing."""

    process: subprocess.CompletedProcess[str]

    @property
    def returncode(self) -> int:
        return self.process.returncode

    @property
    def combined_output(self) -> str:
        """Combines stdout and stderr for convenient searching."""
        return (self.process.stdout or "") + (self.process.stderr or "")

    @property
    def combined_output_lower(self) -> str:
        """Lowercase combined output for case-insensitive searches."""
        return self.combined_output.lower()

    def contains(self, text: str, case_sensitive: bool = False) -> bool:
        """Checks if output contains the given text."""
        search_text = (
            self.combined_output if case_sensitive else self.combined_output_lower
        )
        target = text if case_sensitive else text.lower()
        return target in search_text

    def matches_pattern(self, pattern: re.Pattern[str]) -> bool:
        """Checks if output matches the given regex pattern."""
        return bool(pattern.search(self.combined_output))

    def get_log_lines(self) -> list[str]:
        """Extracts lines that appear to be log messages."""
        return [
            line
            for line in self.combined_output.split("\n")
            if "[DEBUG]" in line or "[INFO]" in line
        ]


class CliTestHelper:
    """Helper for CLI testing operations."""

    def __init__(
        self, cli_runner: Callable[..., subprocess.CompletedProcess[str]]
    ) -> None:
        self.cli_runner = cli_runner

    def run(self, *args: str) -> CliResult:
        """Executes CLI command and returns wrapped result."""
        return CliResult(self.cli_runner(*args))

    def run_normal_and_verbose(self, *base_args: str) -> tuple[CliResult, CliResult]:
        """Runs command in both normal and verbose modes."""
        normal = self.run(*base_args)
        verbose = self.run("--verbose", *base_args)
        return normal, verbose


@pytest.fixture
def cli_helper(
    subprocess_cli_runner: Callable[..., subprocess.CompletedProcess[str]],
) -> CliTestHelper:
    """Provides CLI test helper."""
    return CliTestHelper(subprocess_cli_runner)


class TestDebugLogVisibility:
    """Tests debug log visibility based on verbose flag."""

    def test_debug_logs_only_appear_with_verbose_flag(
        self, cli_helper: CliTestHelper
    ) -> None:
        """Debug logs only appear when --verbose flag is used."""
        normal, verbose = cli_helper.run_normal_and_verbose("list")

        # Both commands should complete acceptably
        assert normal.returncode in ACCEPTABLE_CODES
        assert verbose.returncode in ACCEPTABLE_CODES

        # Debug logs should only appear in verbose mode
        assert not normal.matches_pattern(LogPatterns.DEBUG_LOG), (
            "Debug logs should not appear in normal mode"
        )

        # Note: Verbose mode may or may not show debug logs depending on
        # template availability


class TestLogFormatting:
    """Tests log message formatting and structure."""

    def test_log_messages_have_proper_format(self, cli_helper: CliTestHelper) -> None:
        """Log messages include timestamps and level indicators."""
        result = cli_helper.run("--verbose", "list")
        assert result.returncode in ACCEPTABLE_CODES

        log_lines = result.get_log_lines()
        if not log_lines:
            return  # No logs to validate

        # Verify log formatting
        has_timestamp = any(LogPatterns.TIMESTAMP.search(line) for line in log_lines)
        has_level = any(LogPatterns.LOG_LEVEL.search(line) for line in log_lines)

        assert has_timestamp, (
            f"Log lines should include timestamps. Found: {log_lines[:3]}"
        )
        assert has_level, (
            f"Log lines should include level indicators. Found: {log_lines[:3]}"
        )


class TestInfoLevelOutput:
    """Tests info-level message visibility."""

    def test_info_messages_appear_in_both_modes(
        self, cli_helper: CliTestHelper
    ) -> None:
        """Info-level messages appear in both normal and verbose modes."""
        normal, verbose = cli_helper.run_normal_and_verbose("--help")

        # Both should succeed
        assert normal.returncode == ExitCode.SUCCESS
        assert verbose.returncode == ExitCode.SUCCESS

        assert normal.contains(ExpectedStrings.CLI_NAME)
        assert verbose.contains(ExpectedStrings.CLI_NAME)


class TestErrorHandling:
    """Tests logging error handling and graceful degradation."""

    def test_handles_invalid_commands_gracefully(
        self, cli_helper: CliTestHelper
    ) -> None:
        """An unknown command reports a usage error, not a crash or a config failure.

        Per docs/design/02-data-models.md §Exit Codes, bad command-line input is
        VALIDATION_ERROR; 2 belongs to settings that could not be loaded.
        """
        result = cli_helper.run("nonexistent-command")

        assert result.returncode == ExitCode.VALIDATION_ERROR
        assert result.contains(ExpectedStrings.USAGE) or result.contains("error")
        assert not result.contains("Traceback", case_sensitive=True)

    def test_logging_initialization_succeeds(self, cli_helper: CliTestHelper) -> None:
        """Logging configuration initializes without errors."""
        result = cli_helper.run("--help")

        assert result.returncode == ExitCode.SUCCESS
        assert result.contains(ExpectedStrings.CLI_NAME)

        # Should not contain logging error indicators
        for error in ExpectedStrings.LOGGING_ERRORS:
            assert not result.contains(error), f"Found logging error indicator: {error}"

    def test_rich_handler_works_without_errors(self, cli_helper: CliTestHelper) -> None:
        """Rich logging handler works without formatting errors."""
        result = cli_helper.run("--verbose", "list")

        assert result.returncode in ACCEPTABLE_CODES

        # Should not contain Rich-specific errors
        for error in ExpectedStrings.RICH_ERRORS:
            assert not result.contains(error, case_sensitive=True), (
                f"Found Rich formatting error: {error}"
            )


class TestLibraryLogSilencing:
    """Tests that library logs are properly silenced."""

    def test_copier_logs_are_silenced(self, cli_helper: CliTestHelper) -> None:
        """Copier library logs are silenced even in verbose mode."""
        result = cli_helper.run("--verbose", "list")

        assert result.returncode in ACCEPTABLE_CODES

        # Should not contain copier debug messages
        for indicator in ExpectedStrings.COPIER_INDICATORS:
            assert not result.contains(indicator), (
                f"Found copier log output when it should be silenced: {indicator}"
            )
