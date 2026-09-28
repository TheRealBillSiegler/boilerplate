"""Tests for scripts/boilerplate_cli_svg_themify.py.

Runs the script as a subprocess with ``--help`` rather than importing it, since
its ``argparse`` parser is built inside ``main()`` and exits before any file
I/O happens.
"""

import subprocess
import sys
from pathlib import Path

_SCRIPT = (
    Path(__file__).resolve().parents[2] / "scripts" / "boilerplate_cli_svg_themify.py"
)


class TestInputPathDefault:
    def test_help_text_has_no_backslash_and_names_the_default_path(self) -> None:
        result = subprocess.run(
            [sys.executable, str(_SCRIPT), "--help"],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "\\" not in result.stdout
        assert "docs/assets/boilerplate-cli-logo.svg" in result.stdout
