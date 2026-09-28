"""Tests for `boilerplate graph` command."""

import io
from pathlib import Path
from typing import TYPE_CHECKING

from typer.testing import CliRunner

from boilerplate.cli import app
from boilerplate.cli.commands.graph import present_list, present_tree
from boilerplate.cli.display.core import Display
from boilerplate.composition.models.graph import CompositionGraph, GraphNode

if TYPE_CHECKING:
    from syrupy.assertion import SnapshotAssertion


def _write_tpl(
    dir: Path, name: str, version: str, extends: list[str] | None = None
) -> None:
    tdir = dir / name
    tdir.mkdir()
    (tdir / "copier.yml").touch()
    (tdir / "boilerplate.yml").write_text(
        f"""
        schema_version: "1.0.0"
        name: "{name}"
        description: "{name} template."
        version: "{version}"
        extends: {extends or []}
        """
    )


def test_graph_list_and_tree_behavior(
    tmp_path: Path, typer_cli_runner: CliRunner
) -> None:
    """Tests that graph command produces expected list & tree output formats."""
    _write_tpl(tmp_path, "base", "1.0.0")
    _write_tpl(tmp_path, "mid", "1.0.0", ["base"])
    _write_tpl(tmp_path, "app", "1.0.0", ["mid"])

    # list (default) - verify output content
    r1 = typer_cli_runner.invoke(
        app, ["graph", "app", "--templates-dir", str(tmp_path)]
    )
    assert "Layer" in r1.output
    assert "app" in r1.output and "mid" in r1.output and "base" in r1.output

    # tree - verify output format
    r2 = typer_cli_runner.invoke(
        app,
        ["graph", "app", "--templates-dir", str(tmp_path), "--format", "tree"],
    )
    assert "app@1.0.0" in r2.output


def test_graph_json_output_behavior(
    tmp_path: Path, typer_cli_runner: CliRunner
) -> None:
    """Tests that graph command produces correct JSON output format."""
    _write_tpl(tmp_path, "lib", "1.0.0")
    _write_tpl(tmp_path, "svc", "1.0.0", ["lib"])

    # json to stdout - verify JSON structure
    r1 = typer_cli_runner.invoke(
        app,
        ["graph", "svc", "--templates-dir", str(tmp_path), "--format", "json"],
    )
    assert '"sequence"' in r1.output and '"layers"' in r1.output

    # json to file - verify file creation and content
    out = tmp_path / "graph.json"
    typer_cli_runner.invoke(
        app,
        [
            "graph",
            "svc",
            "--templates-dir",
            str(tmp_path),
            "--format",
            "json",
            "--output",
            str(out),
        ],
    )
    assert out.exists()
    content = out.read_text()
    assert '"svc"' in content and '"lib"' in content and '"sequence"' in content


def test_graph_output_validation_behavior(
    tmp_path: Path, typer_cli_runner: CliRunner
) -> None:
    """Tests that graph command validates --output option usage correctly."""
    _write_tpl(tmp_path, "alpha", "1.0.0")
    r = typer_cli_runner.invoke(
        app,
        [
            "graph",
            "alpha",
            "--templates-dir",
            str(tmp_path),
            "--output",
            str(tmp_path / "x.json"),
        ],
    )
    # Focus on behavior: validation error message
    assert "--output only works with --format json" in r.output


def test_graph_output_validation_error_carries_the_error_prefix(
    tmp_path: Path, typer_cli_runner: CliRunner
) -> None:
    """The --output/--format conflict reads Error:, like every other error.

    Regression: this message skipped the Error: prefix that design 07's
    Error Message Format requires on every error line, even one raised
    outside the BP-coded boundary.
    """
    _write_tpl(tmp_path, "alpha", "1.0.0")
    r = typer_cli_runner.invoke(
        app,
        [
            "graph",
            "alpha",
            "--templates-dir",
            str(tmp_path),
            "--output",
            str(tmp_path / "x.json"),
        ],
    )
    assert "Error: --output only works with --format json." in r.output


def test_render_graph_list_output_snapshot(
    captured_display: tuple[Display, io.StringIO],
    snapshot: "SnapshotAssertion",
) -> None:
    """Verifies graph list rendering produces consistent output."""
    display, output = captured_display

    # Create mock nodes
    node1 = GraphNode(name="base", version="1.0.0", path=Path("templates/base"))
    node2 = GraphNode(name="addon", version="2.0.0", path=Path("templates/addon"))

    # Create mock graph
    graph = CompositionGraph(
        sequence=["base", "addon"], nodes={"base": node1, "addon": node2}, edges={}
    )

    present_list(graph, display)

    result = output.getvalue()
    # Snapshot the complete graph list output
    assert result == snapshot


def test_render_graph_tree_output_snapshot(
    captured_display: tuple[Display, io.StringIO],
    snapshot: "SnapshotAssertion",
) -> None:
    """Verifies graph tree rendering produces consistent output."""
    display, output = captured_display

    # Create mock nodes
    node1 = GraphNode(name="base", version="1.0.0", path=Path("templates/base"))
    node2 = GraphNode(name="addon", version="2.0.0", path=Path("templates/addon"))
    node3 = GraphNode(name="custom", version="1.2.3", path=Path("templates/custom"))

    # Create mock graph with tree structure
    graph = CompositionGraph(
        sequence=["base", "addon", "custom"],
        nodes={"base": node1, "addon": node2, "custom": node3},
        edges={"base": ["addon"], "addon": ["custom"], "custom": []},
    )

    present_tree(graph, display)

    result = output.getvalue()
    # Snapshot the complete graph tree output
    assert result == snapshot
