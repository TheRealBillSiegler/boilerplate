"""Logging configuration for the Boilerplate CLI."""
# Spec: docs/design/07-operational-quality.md §Structured Logging

import json
import logging
import os
import sys
import uuid
from datetime import UTC, datetime
from logging import getLogger

from rich.logging import RichHandler


class JsonLogFormatter(logging.Formatter):
    """Formats each log record as one strict-JSON object on a single line.

    Emits the required structured-log fields from
    docs/design/07-operational-quality.md §Structured Logging: ``phase``,
    ``operation``, ``request_id``, ``success``, and ``error_code`` when
    ``success`` is false. Emitters supply ``phase``, ``operation``,
    ``success``, ``error_code``, and ``template`` via ``extra``; records
    without them fall back to phase ``internal``, the emitting function
    name as ``operation``, and success derived from the record level
    (ERROR and above report failure).
    """

    def __init__(self, request_id: str) -> None:
        """Initialize with the per-invocation correlation ID.

        Args:
            request_id: Correlation ID attached to every record. Taken
                verbatim from ``BOILERPLATE_REQUEST_ID`` when set, else
                auto-generated once per invocation.
        """
        super().__init__()
        self._request_id = request_id

    def format(self, record: logging.LogRecord) -> str:
        """Render the record as a single-line JSON object.

        Args:
            record: The log record to serialize.

        Returns:
            A strict-JSON object string without embedded newlines.
        """
        success = bool(getattr(record, "success", record.levelno < logging.ERROR))
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "phase": getattr(record, "phase", "internal"),
            "operation": getattr(record, "operation", record.funcName),
            "message": record.getMessage(),
            "request_id": self._request_id,
            "success": success,
        }
        template = getattr(record, "template", None)
        if template is not None:
            payload["template"] = template
        if not success:
            payload["error_code"] = getattr(record, "error_code", None)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(debug: bool = False, ci: bool = False) -> None:
    """Configure logging for the Boilerplate CLI.

    Rich console output when stderr is a TTY (and ``NO_COLOR`` is unset);
    otherwise one strict-JSON object per log event on stderr, per
    docs/design/07-operational-quality.md §Log Output. ``--ci`` forces the
    JSON path regardless of TTY.

    Args:
        debug: If True, set to DEBUG level; otherwise INFO.
        ci: If True, emit structured JSON even when stderr is a TTY.

    Note:
        To customize dependency logger levels after configuration:
        getLogger("copier").setLevel(logging.WARNING)
    """
    level = logging.DEBUG if debug else logging.INFO

    handler: logging.Handler
    if not ci and sys.stderr.isatty() and "NO_COLOR" not in os.environ:
        handler = RichHandler(markup=True, level=level)
    else:
        # BOILERPLATE_REQUEST_ID is used verbatim when set, enabling parent
        # service correlation; otherwise one ID is shared per invocation.
        request_id = os.environ.get("BOILERPLATE_REQUEST_ID") or str(uuid.uuid4())
        handler = logging.StreamHandler(stream=sys.stderr)
        handler.setLevel(level)
        handler.setFormatter(JsonLogFormatter(request_id))

    logging.basicConfig(
        level=level,
        handlers=[handler],
        force=True,
    )

    # Explicitly set boilerplate logger level for tests that check it
    getLogger("boilerplate").setLevel(level)
