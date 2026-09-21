"""Tests for display functionality.

Snapshot Testing Guide:
======================
Snapshots capture the exact output of rich components and verify
they match expectations.

To update snapshots when output changes:
1. Review the changes carefully to ensure they're intentional
2. Run: pytest tests/boilerplate/cli/display/test_core.py --snapshot-update
3. Commit the updated snapshot files

Note: Snapshot tests are automatically grouped to run serially to avoid file
      conflicts, while other tests continue to run in parallel.
"""

import io
import json
from typing import TYPE_CHECKING

import pytest
from pytest_mock import MockerFixture
from rich.console import Console
from rich.style import Style
from rich.theme import Theme

from boilerplate.cli.display.core import DEFAULT_THEME, Display

if TYPE_CHECKING:
    from pathlib import Path

    from syrupy.assertion import SnapshotAssertion


def test_default_theme_has_required_styles() -> None:
    """Ensures DEFAULT_THEME includes all expected styles with correct attributes."""
    expected = {
        "info": {"color": "cyan"},
        "success": {"color": "green"},
        "warning": {"color": "yellow"},
        "error": {"bold": True, "color": "red"},
    }

    for key, props in expected.items():
        assert key in DEFAULT_THEME.styles
        style = DEFAULT_THEME.styles[key]
        assert isinstance(style, Style)
        for attr, expected_value in props.items():
            value = getattr(style, attr)
            if attr == "color" and value is not None:
                assert value.name == expected_value
            else:
                assert value == expected_value


def test_custom_theme_overrides_default() -> None:
    """Verifies that custom themes actually override default styling."""
    custom_theme = Theme({"info": "magenta", "success": "blue"})
    display = Display(theme=custom_theme)

    # Verify the custom theme is used
    assert display.theme.styles["info"].color.name == "magenta"  # type: ignore[union-attr]
    assert display.theme.styles["success"].color.name == "blue"  # type: ignore[union-attr]

    # Verify fallback to default for undefined styles
    assert "warning" in display.theme.styles  # Should inherit from default


class TestAccessibleEnvFlag:
    """BOILERPLATE_ACCESSIBLE follows the shared env_flag truthiness rule."""

    @pytest.fixture(autouse=True)
    def _isolate_color_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Keep NO_COLOR/FORCE_COLOR from leaking into no_color detection."""
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.delenv("FORCE_COLOR", raising=False)

    @pytest.mark.parametrize("value", ["1", "true", "on", "yes", "TRUE"])
    def test_truthy_values_enable_accessible_mode(
        self, monkeypatch: pytest.MonkeyPatch, value: str
    ) -> None:
        monkeypatch.setenv("BOILERPLATE_ACCESSIBLE", value)
        display = Display()
        assert display.console.no_color

    @pytest.mark.parametrize("value", ["0", "false", "FALSE", "", "   "])
    def test_falsy_values_leave_accessible_mode_off(
        self, monkeypatch: pytest.MonkeyPatch, value: str
    ) -> None:
        monkeypatch.setenv("BOILERPLATE_ACCESSIBLE", value)
        display = Display()
        assert not display.console.no_color

    def test_unset_leaves_accessible_mode_off(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("BOILERPLATE_ACCESSIBLE", raising=False)
        display = Display()
        assert not display.console.no_color


class TestQuiet:
    """quiet=True suppresses info/success chatter; warnings and errors still print."""

    def test_quiet_suppresses_info_and_success(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        display = Display(quiet=True)
        display.info("info message")
        display.success("success message")
        assert capsys.readouterr().out == ""

    def test_quiet_keeps_warnings_and_errors(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        display = Display(quiet=True)
        display.warning("warn message")
        display.error("error message")
        captured = capsys.readouterr()
        assert "warn message" in captured.err
        assert "error message" in captured.err

    def test_default_prints_info_and_success(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        display = Display()
        display.info("info message")
        display.success("success message")
        captured = capsys.readouterr()
        assert "info message" in captured.out
        assert "success message" in captured.out


class TestTablePathLinks:
    """Path columns emit file:// links with forward slashes."""

    def test_absolute_path_gets_file_link(
        self, mocker: MockerFixture, tmp_path: "Path"
    ) -> None:
        """An absolute path is linked via its file:// URI (forward slashes)."""
        display = Display()
        print_spy = mocker.patch.object(display.console, "print")
        target = tmp_path / "demo"
        display.table(("Name", "Path"), [("x", str(target))], path_column_index=1)
        table = print_spy.call_args.args[0]
        cell = next(iter(table.columns[1].cells))
        assert f"[link={target.as_uri()}]" in cell
        assert "\\" not in target.as_uri()

    def test_relative_path_gets_no_link(self, mocker: MockerFixture) -> None:
        """A relative path has no file URI; the cell stays plain."""
        display = Display()
        print_spy = mocker.patch.object(display.console, "print")
        display.table(("Name", "Path"), [("x", "templates/web")], path_column_index=1)
        table = print_spy.call_args.args[0]
        cell = next(iter(table.columns[1].cells))
        assert cell == "templates/web"


@pytest.mark.parametrize(
    "method_name,message",
    [
        ("info", "Information message"),
        ("success", "Success message"),
        ("warning", "Warning message"),
        ("error", "Error message"),
    ],
)
def test_message_methods_output_snapshot(
    captured_display: tuple[Display, io.StringIO],
    method_name: str,
    message: str,
    snapshot: "SnapshotAssertion",
) -> None:
    """Verifies message methods produce consistent formatted output."""
    display, output = captured_display
    getattr(display, method_name)(message)

    result = output.getvalue()
    # Keep one explicit assertion for message content
    assert message in result
    # Use snapshot for consistent formatting
    assert result == snapshot


def test_table_empty_data_snapshot(
    captured_display: tuple[Display, io.StringIO],
    snapshot: "SnapshotAssertion",
) -> None:
    """Verifies table gracefully handles empty data with consistent formatting."""
    display, output = captured_display

    # Empty table should not crash
    display.table(["Header1", "Header2"], [])
    result = output.getvalue()

    # Keep explicit assertions for key functionality
    assert "Header1" in result
    assert "Header2" in result
    # Snapshot the complete output format
    assert result == snapshot


def test_table_unicode_content_snapshot(
    captured_display: tuple[Display, io.StringIO],
    snapshot: "SnapshotAssertion",
) -> None:
    """Verifies table handles unicode characters with consistent formatting."""
    display, output = captured_display

    headers = ["名前", "値"]
    rows = [("测试", "🚀"), ("データ", "✅")]

    display.table(headers, rows)
    result = output.getvalue()

    # Keep explicit assertions for content presence
    for header in headers:
        assert header in result
    for row in rows:
        for cell in row:
            assert cell in result
    # Snapshot the complete table formatting
    assert result == snapshot


class TestWriteByteExact:
    """write() reaches stdout byte-exact for machine-readable payloads.

    Rich's Console.print, used unadorned, hard-wraps at console width and
    interprets ``[...]`` spans as markup -- both corrupt JSON/YAML content
    such as long single-line dumps or YAML flow sequences.
    """

    def test_long_json_line_not_wrapped(
        self, captured_display: tuple[Display, io.StringIO]
    ) -> None:
        """A JSON line wider than the console width is not hard-wrapped."""
        display, output = captured_display
        payload = json.dumps(
            {
                "templates": [
                    {
                        "name": f"template-{i}",
                        "version": "1.0.0",
                        "description": "a description long enough to force wrapping",
                        "path": f"/some/long/path/to/templates/template-{i}",
                    }
                    for i in range(3)
                ]
            }
        )
        assert len(payload) > 80  # must exceed the fixture's fixed width

        display.write(payload, end="")

        assert output.getvalue() == payload
        assert json.loads(output.getvalue()) == json.loads(payload)

    def test_yaml_flow_sequence_not_treated_as_markup(
        self, captured_display: tuple[Display, io.StringIO]
    ) -> None:
        """A YAML flow sequence like ``[base, addon]`` is not swallowed as markup."""
        display, output = captured_display
        payload = "name: demo\nextends: [base, addon]\n"

        display.write(payload, end="")

        assert output.getvalue() == payload

    def test_literal_bracket_text_printed_verbatim(
        self, captured_display: tuple[Display, io.StringIO]
    ) -> None:
        """Text that looks like Rich markup is printed literally, not parsed."""
        display, output = captured_display
        payload = "[bold]not a style[/bold]"

        display.write(payload, end="")

        assert output.getvalue() == payload

    def test_no_ansi_codes_injected_under_forced_color(self) -> None:
        """Highlighting stays off for write() even with color forced on.

        Without ``highlight=False``, Rich's ReprHighlighter would inject
        ANSI style codes around quoted strings/numbers when color is
        active, breaking byte-exactness for ``--format json --color always``.
        """
        display = Display()
        buffer = io.StringIO()
        console = Console(
            theme=display.theme,
            file=buffer,
            width=200,
            color_system="truecolor",
            force_terminal=True,
            legacy_windows=False,
        )
        display.console = console

        payload = json.dumps({"name": "boilerplate", "version": "1.2.3"})
        display.write(payload, end="")

        assert buffer.getvalue() == payload


def test_table_mismatched_columns_snapshot(
    captured_display: tuple[Display, io.StringIO],
    snapshot: "SnapshotAssertion",
) -> None:
    """Verifies table handles mismatched column counts with consistent formatting."""
    display, output = captured_display

    headers = ["A", "B", "C"]
    rows = [
        ("1", "2"),  # Missing column
        ("x", "y", "z", "extra"),  # Extra column
        ("complete", "row", "here"),  # Correct
    ]

    # Should not crash
    display.table(headers, rows)
    result = output.getvalue()
    # Keep basic non-crash assertion
    assert len(result.strip()) > 0
    # Snapshot the handling of mismatched columns
    assert result == snapshot
