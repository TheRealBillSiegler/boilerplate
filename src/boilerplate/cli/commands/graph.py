"""`boilerplate graph` command for dependency graph visualization.

Provides three output formats for analyzing template dependency relationships:
- list: Numbered table showing execution sequence
- tree: Hierarchical dependency structure
- json: Machine-readable graph data with sequence and layers
"""

from enum import StrEnum
from logging import getLogger
from pathlib import Path

import typer
from rich.tree import Tree

from boilerplate.cli.common import OUTPUT_OPTION, TEMPLATES_DIR_OPTION
from boilerplate.cli.display import Display
from boilerplate.cli.utils import cli_error_handler, compute_composition
from boilerplate.composition.models.graph import CompositionGraph
from boilerplate.composition.serialization.composition_writer_json import dump_json
from boilerplate.constants import ExitCode

_logger = getLogger(__name__)


class GraphFormat(StrEnum):
    """Supported output formats for dependency graph visualization."""

    TABLE = "table"
    TREE = "tree"
    JSON = "json"


FORMAT_OPTION = typer.Option(
    GraphFormat.TABLE,
    "--format",
    help="Output format: table, tree, or json.",
)


def present_list(graph: CompositionGraph, display: Display) -> None:
    """Present dependency graph as a numbered table.

    Args:
        graph: Composition graph to render
        display: Display instance for output
    """
    items: list[tuple[str, str, str]] = []
    for spec in graph.sequence:
        node = graph.nodes.get(spec)
        if node is not None:
            items.append((node.name, node.version, node.path.as_posix()))

    headers = ["#", "Layer", "Version", "Path"]
    rows = [
        (str(i + 1), name, version, path)
        for i, (name, version, path) in enumerate(items)
    ]
    display.table(
        headers,
        rows,
        expand=True,
        wrap_last_column=True,
        path_column_index=3,
    )


def present_tree(graph: CompositionGraph, display: Display) -> None:
    """Present dependency graph as a hierarchical tree.

    Args:
        graph: Composition graph to render
        display: Display instance for output
    """
    label_for = {spec: f"{n.name}@{n.version}" for spec, n in graph.nodes.items()}
    parent_to_children = graph.edges

    parents = set(parent_to_children.keys())
    children = {child for kids in parent_to_children.values() for child in kids}
    roots = sorted(parents - children) if parents else []

    def add_children(node: Tree, parent: str) -> None:
        for child in parent_to_children.get(parent, []):
            label = label_for.get(child, child)
            child_node = node.add(label)
            add_children(child_node, child)

    def print_plain(parent: str, indent: int) -> None:
        display.console.print("  " * indent + f"- {label_for.get(parent, parent)}")
        for child in parent_to_children.get(parent, []):
            print_plain(child, indent + 1)

    if (
        display.console.is_terminal
        and display.console.color_system is not None
        and roots
    ):
        for root in roots:
            root_label = label_for.get(root, root)
            tree = Tree(root_label, style="info")
            add_children(tree, root)
            display.console.print(tree)
    else:
        if not roots and parents:
            roots = [sorted(parents)[0]]
        for root in roots:
            print_plain(root, 0)


@cli_error_handler
def graph(
    ctx: typer.Context,
    template: str = typer.Argument(
        ..., help="Template reference (name or name@version)."
    ),
    templates_dir: Path | None = TEMPLATES_DIR_OPTION,
    format: GraphFormat = FORMAT_OPTION,
    output: Path | None = OUTPUT_OPTION,
) -> None:
    """Show dependency execution sequence for a template.

    Visualizes template dependencies in three formats:

    - table: Execution order as numbered table with paths
    - tree: Hierarchical dependency structure
    - json: Complete graph data (sequence + layers) for tools

    The graph shows how templates depend on each other and the order
    they would execute during composition.
    """
    cli_context = ctx.obj
    display: Display = cli_context.display
    settings = cli_context.settings

    if output is not None and format is not GraphFormat.JSON:
        display.error("Output option requires JSON format.")
        raise typer.Exit(code=ExitCode.VALIDATION_ERROR)

    comp = compute_composition(template, templates_dir, settings)
    layer_count = len(comp.graph.sequence)
    _logger.debug("Dependency graph built: %d templates", layer_count)

    if format is GraphFormat.JSON:
        text = dump_json(comp.graph.sequence_payload())
        if output is not None:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(text, encoding="utf-8")
        else:
            display.write(text, end="")
        _logger.info("Graph command completed: %d templates (format=json)", layer_count)
        return

    if format is GraphFormat.TREE:
        present_tree(comp.graph, display)
    else:
        present_list(comp.graph, display)

    _logger.debug(
        "Graph command completed: %d templates (format=%s)",
        layer_count,
        format.value,
    )


__all__ = ["graph"]
