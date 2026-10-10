"""What the banner needs to know about the terminal it prints to."""

from pydantic import BaseModel, ConfigDict


class TerminalFacts(BaseModel):
    """What the banner needs to know about the terminal it prints to.

    ``terminal_probe.read_terminal_facts`` reads these from the console and the
    environment; ``banner.build_banner`` decides from them alone.

    Attributes:
        interactive: stdout is a terminal, and ``TERM`` is not ``dumb`` or
            ``unknown``.
        columns: The terminal's width, in columns.
        lines: The terminal's height, in lines.
        braille: The terminal can be expected to draw braille: stdout encodes
            UTF-8 and ``TERM`` is not ``linux``.
        ascii_only: The console prints without color, which
            docs/design/05-cli-reference.md also limits to printable ASCII.
        accessible: ``BOILERPLATE_ACCESSIBLE`` is enabled, or the system
            reports a running screen reader.
        opted_out: ``BOILERPLATE_NO_BANNER`` is enabled.
        cell_shape: Cell height divided by cell width, when the terminal
            reports its size in pixels; otherwise ``None``.
    """

    model_config = ConfigDict(frozen=True)

    interactive: bool
    columns: int
    lines: int
    braille: bool
    ascii_only: bool
    accessible: bool
    opted_out: bool
    cell_shape: float | None = None
