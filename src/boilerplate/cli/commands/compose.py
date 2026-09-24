"""Shows the merged configuration a template composes, layer by layer.

Section export and formatting live here rather than on ``Composition``: they
are presentation concerns owned by the CLI, and the domain model stays free of
filesystem writes and display strings.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from logging import getLogger
from pathlib import Path
from typing import cast

import typer
from slugify import slugify

from boilerplate import __version__
from boilerplate.cli.common import (
    QUIET_OPTION,
    TEMPLATES_DIR_OPTION,
)
from boilerplate.cli.display import Display
from boilerplate.cli.types import DataFormat, Section
from boilerplate.cli.utils import (
    cli_error_handler,
    compute_composition,
    ensure_verbose_quiet_exclusive,
)
from boilerplate.composition.models import Composition, CompositionLayer
from boilerplate.composition.models.json_types import JSON
from boilerplate.composition.serialization import (
    dump_json,
    dump_yaml,
    write_json,
    write_yaml,
)

_logger = getLogger(__name__)


def validate_sections_param(value: str | None) -> str | None:
    """Validate sections parameter for Typer callback."""
    if value is not None and value.strip() == "":
        # Get all valid sections for error message
        valid_sections = {s.value for s in Section}
        allowed_csv = ",".join(sorted(valid_sections))
        raise typer.BadParameter(
            f"Select at least one section. Allowed: {allowed_csv}."
        )
    return value


def parse_sections(
    sections_csv: str | None,
    all_flag: bool,
    stats_flag: bool = False,
) -> list[Section]:
    """Parse and validate the sections selection, preserving order."""
    if stats_flag:
        return [Section.STATS]
    if all_flag:
        return [
            Section.STATS,
            Section.FINAL,
            Section.LAYERS,
            Section.STATES,
            Section.DELTAS,
        ]

    if not sections_csv:
        return [Section.FINAL]  # Default to final only

    # Parse CSV and validate
    sections = [s.strip() for s in sections_csv.split(",") if s.strip()]
    if not sections:
        raise typer.BadParameter("Select at least one section to output.")

    # Validate sections against enum values
    valid_sections = {s.value for s in Section}
    unknown = [s for s in sections if s not in valid_sections]
    if unknown:
        allowed_csv = ",".join(sorted(valid_sections))
        raise typer.BadParameter(
            f"Unknown section(s): {', '.join(unknown)}. Allowed: {allowed_csv}."
        )

    return [Section(s) for s in sections]


def _layer_mapping(layer: CompositionLayer, section: Section) -> dict[str, JSON]:
    """Return the mapping a per-layer section renders for one layer.

    Args:
        layer: The layer to read.
        section: One of ``LAYERS``, ``STATES``, or ``DELTAS``.

    Returns:
        The layer's values, state, or delta.
    """
    if section is Section.LAYERS:
        return layer.values
    if section is Section.STATES:
        return layer.state
    return layer.delta_view


def write_sections(
    composition: Composition,
    output_dir: Path,
    sections: Sequence[Section],
    format: DataFormat,
) -> dict[str, JSON]:
    """Write the selected sections to a directory alongside a manifest.

    Args:
        composition: Composition to export.
        output_dir: Destination directory for the artifacts.
        sections: Sections to export.
        format: Serialization format for the section files.

    Returns:
        Manifest describing the files written.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    written_files: list[str] = []
    write_fn = write_yaml if format is DataFormat.YAML else write_json
    ext = f".{format.value}"

    if Section.FINAL in sections:
        path = output_dir / f"final{ext}"
        write_fn(composition.final, path)
        written_files.append(str(path))

    for index, layer in enumerate(composition.layers, start=1):
        prefix = f"{index:02d}-{slugify(layer.name)}"
        for section, filename_part in (
            (Section.LAYERS, "values"),
            (Section.STATES, "state"),
            (Section.DELTAS, "delta"),
        ):
            if section in sections:
                path = output_dir / f"{prefix}-{filename_part}{ext}"
                write_fn(_layer_mapping(layer, section), path)
                written_files.append(str(path))

    if Section.STATS in sections:
        path = output_dir / "stats.json"
        write_json(composition.stats_mapping(), path)
        written_files.append(str(path))

    manifest: dict[str, JSON] = {
        "schema": "boilerplate/compose-index@1",
        "version": __version__,
        "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
        "format": format.value,
        "sections": cast(list[JSON], sorted({s.value for s in sections})),
        "sources": cast(list[JSON], [str(layer.path) for layer in composition.layers]),
        "files": cast(list[JSON], written_files),
    }
    write_json(manifest, output_dir / "_index.json")
    return manifest


def format_sections(
    composition: Composition,
    sections: Sequence[Section],
    format: DataFormat,
) -> dict[Section, str]:
    """Render the selected sections as text for stdout.

    Args:
        composition: Composition to render.
        sections: Sections to render, in output order.
        format: Serialization format for section bodies.

    Returns:
        Rendered text keyed by section.
    """
    dump_fn = dump_yaml if format is DataFormat.YAML else dump_json
    result: dict[Section, str] = {}

    for section in sections:
        if section is Section.FINAL:
            result[section] = dump_fn(composition.final)
        elif section is Section.STATS:
            result[section] = dump_fn(composition.stats_mapping())
        else:
            parts: list[str] = []
            for index, layer in enumerate(composition.layers, start=1):
                parts.append(
                    f"Layer {index:02d}: {layer.name}@{layer.version}"
                    f" — {section.value[:-1]}"
                )
                parts.append(dump_fn(_layer_mapping(layer, section)))
            result[section] = "\n".join(parts)

    return result


# Typer options
SECTIONS_OPTION = typer.Option(
    None,
    "--sections",
    help="Sections to show, comma-separated: final, layers, states, deltas, stats.",
    callback=validate_sections_param,
)
ALL_OPTION = typer.Option(False, "--all", help="Show every section.")
STATS_OPTION = typer.Option(False, "--stats", help="Show only the summary.")
FORMAT_OPTION = typer.Option(
    DataFormat.YAML, "--format", help="Output format: yaml or json."
)
OUTPUT_OPTION = typer.Option(
    None, "--output", "-o", help="Directory to write the sections into."
)


@cli_error_handler
def compose(
    ctx: typer.Context,
    template: str = typer.Argument(..., help="Template to use (name or name@version)."),
    sections: str | None = SECTIONS_OPTION,
    all_sections: bool = ALL_OPTION,
    stats: bool = STATS_OPTION,
    format: DataFormat = FORMAT_OPTION,
    output: Path | None = OUTPUT_OPTION,
    quiet: bool = QUIET_OPTION,
    templates_dir: Path | None = TEMPLATES_DIR_OPTION,
) -> None:
    """Show the merged configuration a template composes, layer by layer.

    - final: the fully merged configuration
    - layers: each layer's own values
    - states: each layer's configuration after it applies
    - deltas: what each layer changed
    - stats: summary counts

    Prints to stdout by default. --output writes each section to a file in a directory.
    """
    cli_context = ctx.obj
    display: Display = cli_context.display
    # The global --quiet only parses before the subcommand; honor either position.
    quiet = quiet or cli_context.quiet
    # The root callback only sees pre-subcommand flags, so re-check exclusivity
    # against the merged value.
    ensure_verbose_quiet_exclusive(cli_context.verbose, quiet)

    # Parse and validate sections
    chosen_sections = parse_sections(sections, all_sections, stats)

    # Validate output path if provided
    if output is not None and output.exists() and output.is_file():
        raise typer.BadParameter("Output path points to a file; provide a directory.")

    # Determine what data to capture
    include_states = Section.STATES in chosen_sections
    include_deltas = Section.DELTAS in chosen_sections

    composition = compute_composition(
        template,
        templates_dir,
        cli_context.settings,
        include_states=include_states,
        include_deltas=include_deltas,
    )
    layer_count = len(composition.sequence)
    _logger.debug("Composition built: %d layers", layer_count)

    # Write artifacts to directory if requested
    if output is not None:
        manifest = write_sections(composition, output, chosen_sections, format)
        if not quiet:
            files_list = manifest.get("files", [])
            file_count = len(files_list) if isinstance(files_list, list) else 0
            display.info(f"Wrote {file_count} files to {output}")
        _logger.debug("Composition artifacts written: %s", output)

    # Print to stdout unless quiet
    if not quiet:
        # Show what templates are being composed together
        sequence_text = " → ".join(composition.sequence)
        display.info(f"Layers: {sequence_text}")

        section_data = format_sections(composition, chosen_sections, format)

        # Print each section uniformly
        for section in chosen_sections:
            if section in section_data:
                display.write_line(section.value.upper())
                display.write(section_data[section], end="")

    _logger.debug(
        "Compose command completed: %d layers (sections=%s)",
        layer_count,
        ",".join(s.value for s in chosen_sections),
    )


__all__ = ["compose"]
