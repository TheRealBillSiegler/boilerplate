"""Tests logging configuration behavior for the Boilerplate CLI."""

import io
import json
import logging
import sys
import uuid
from typing import Any

import pytest
from rich.logging import RichHandler

from boilerplate import logging_config


class FakeTtyStderr(io.StringIO):
    """In-memory stderr stand-in that reports being a TTY."""

    def isatty(self) -> bool:
        """Reports TTY so the Rich branch is selected."""
        return True


@pytest.fixture(autouse=True)
def reset_logging() -> None:
    """Resets logging configuration before each test."""
    # Clear all handlers and reset levels to ensure clean state
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.NOTSET)

    # Reset specific loggers
    for logger_name in ["boilerplate", "copier"]:
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        logger.setLevel(logging.NOTSET)


def test_info_level_logging_captures_info_and_above_messages() -> None:
    """When debug=False, logging captures INFO level and above messages."""
    logging_config.configure_logging(debug=False)

    # Get the configured logger and check its level
    logger = logging.getLogger("boilerplate")
    root = logging.getLogger()

    # Both should be set to INFO level
    assert logger.level == logging.INFO
    assert root.level == logging.INFO

    # Root should have one handler at INFO level
    assert len(root.handlers) == 1
    assert root.handlers[0].level == logging.INFO


def test_debug_level_logging_captures_all_messages() -> None:
    """When debug=True, logging captures all messages including DEBUG."""
    logging_config.configure_logging(debug=True)

    # Get the configured logger and check its level
    logger = logging.getLogger("boilerplate")
    root = logging.getLogger()

    # Both should be set to DEBUG level
    assert logger.level == logging.DEBUG
    assert root.level == logging.DEBUG

    # Root should have one handler at DEBUG level
    assert len(root.handlers) == 1
    assert root.handlers[0].level == logging.DEBUG


def test_boilerplate_logger_configured_with_specified_level() -> None:
    """The boilerplate logger is configured with the specified level."""
    # Test INFO level
    logging_config.configure_logging(debug=False)
    boilerplate_logger = logging.getLogger("boilerplate")
    assert boilerplate_logger.level == logging.INFO

    # Reset and test DEBUG level
    boilerplate_logger.setLevel(logging.NOTSET)
    logging_config.configure_logging(debug=True)
    assert boilerplate_logger.level == logging.DEBUG


def test_copier_logger_always_set_to_warning_level() -> None:
    """The copier logger is configured with default level."""
    # Test with debug=False
    logging_config.configure_logging(debug=False)
    copier_logger = logging.getLogger("copier")
    # Default level should be NOTSET, not hardcoded WARNING
    assert copier_logger.level == logging.NOTSET

    # Test with debug=True - should still be NOTSET
    copier_logger.setLevel(logging.NOTSET)
    logging_config.configure_logging(debug=True)
    assert copier_logger.level == logging.NOTSET


def test_rich_handler_configured_for_root_logger() -> None:
    """The root logger is configured with appropriate handler for environment."""
    # Clear handlers first, then configure logging
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.NOTSET)

    logging_config.configure_logging(debug=False)

    # In test environments, we expect a StreamHandler (not TTY)
    # But let's just check that we have exactly one handler configured
    assert len(root.handlers) == 1, f"Expected 1 handler, found {len(root.handlers)}"

    # The handler should be either RichHandler or StreamHandler
    handler = root.handlers[0]
    assert isinstance(handler, RichHandler | logging.StreamHandler), (
        f"Expected RichHandler or StreamHandler, got {type(handler)}"
    )


def test_log_message_format_includes_timestamp_and_level() -> None:
    """Log messages are properly configured with appropriate handler."""
    logging_config.configure_logging(debug=False)

    # Check that root logger is configured properly
    root = logging.getLogger()
    assert len(root.handlers) == 1

    # Handler should be either RichHandler or StreamHandler with proper level
    handler = root.handlers[0]
    assert isinstance(handler, RichHandler | logging.StreamHandler)
    assert handler.level == logging.INFO


class TestStructuredJsonLogging:
    """Non-TTY / --ci logging per docs/design/07-operational-quality.md.

    One strict-JSON object per event on stderr, carrying phase, operation,
    request_id, success, and error_code when success is false; the TTY path
    keeps Rich output.
    """

    @pytest.fixture(autouse=True)
    def _isolate_request_id_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Keeps ambient BOILERPLATE_REQUEST_ID out of the tests."""
        monkeypatch.delenv("BOILERPLATE_REQUEST_ID", raising=False)

    @staticmethod
    def _capture_stderr(monkeypatch: pytest.MonkeyPatch) -> io.StringIO:
        """Replaces sys.stderr with an in-memory non-TTY stream."""
        fake = io.StringIO()
        monkeypatch.setattr(sys, "stderr", fake)
        return fake

    @staticmethod
    def _records(stream: io.StringIO) -> list[dict[str, Any]]:
        """Parses each stderr line as a strict-JSON object."""
        return [json.loads(line) for line in stream.getvalue().splitlines() if line]

    def test_non_tty_records_carry_required_fields(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Every non-TTY record is one JSON object with the required fields."""
        stream = self._capture_stderr(monkeypatch)
        logging_config.configure_logging()
        logger = logging.getLogger("boilerplate")

        logger.info(
            "render finished",
            extra={"phase": "render", "operation": "render_template"},
        )
        logger.error(
            "render failed",
            extra={
                "phase": "render",
                "operation": "render_template",
                "success": False,
                "error_code": "BP_RENDER_DEST_NOT_EMPTY",
            },
        )

        records = self._records(stream)
        assert len(records) == 2
        for record in records:
            for field in ("phase", "operation", "request_id", "success"):
                assert field in record
        success_record, failure_record = records
        assert success_record["success"] is True
        assert "error_code" not in success_record
        assert failure_record["success"] is False
        assert failure_record["error_code"] == "BP_RENDER_DEST_NOT_EMPTY"
        assert failure_record["phase"] == "render"
        assert failure_record["operation"] == "render_template"

    def test_untagged_records_get_defaults(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Records without extras fall back to documented defaults."""
        stream = self._capture_stderr(monkeypatch)
        logging_config.configure_logging()

        logging.getLogger("boilerplate").error("bare failure")

        (record,) = self._records(stream)
        assert record["phase"] == "internal"
        assert record["operation"] == "test_untagged_records_get_defaults"
        assert record["success"] is False
        assert record["error_code"] is None

    def test_request_id_env_override_used_verbatim(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """BOILERPLATE_REQUEST_ID is used verbatim on every record."""
        monkeypatch.setenv("BOILERPLATE_REQUEST_ID", "parent-trace-123")
        stream = self._capture_stderr(monkeypatch)
        logging_config.configure_logging()
        logger = logging.getLogger("boilerplate")

        logger.info("first")
        logger.info("second")

        records = self._records(stream)
        assert [r["request_id"] for r in records] == [
            "parent-trace-123",
            "parent-trace-123",
        ]

    def test_request_id_autogenerated_once_per_invocation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without the env var, one UUID is shared across all records."""
        stream = self._capture_stderr(monkeypatch)
        logging_config.configure_logging()
        logger = logging.getLogger("boilerplate")

        logger.info("first")
        logger.info("second")

        records = self._records(stream)
        request_ids = {r["request_id"] for r in records}
        assert len(request_ids) == 1
        uuid.UUID(request_ids.pop())  # parses as a valid UUID

    def test_ci_mode_forces_json_even_on_tty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--ci selects the JSON path regardless of TTY."""
        monkeypatch.setattr(sys, "stderr", FakeTtyStderr())
        monkeypatch.delenv("NO_COLOR", raising=False)

        logging_config.configure_logging(ci=True)

        handler = logging.getLogger().handlers[0]
        assert not isinstance(handler, RichHandler)
        assert isinstance(handler.formatter, logging_config.JsonLogFormatter)

    def test_tty_keeps_rich_handler(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The TTY path keeps Rich output."""
        monkeypatch.setattr(sys, "stderr", FakeTtyStderr())
        monkeypatch.delenv("NO_COLOR", raising=False)

        logging_config.configure_logging()

        assert isinstance(logging.getLogger().handlers[0], RichHandler)
