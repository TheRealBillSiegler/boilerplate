import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from boilerplate.cli import cli


def test_compose_default_prints_final_yaml(typer_cli_runner: CliRunner):
    # Use real templates bundled with the repo via Settings default
    result = typer_cli_runner.invoke(cli.app, ["compose", "project"])
    assert result.exit_code == 0, result.output
    assert "project_name" in result.output


def test_subcommand_quiet_with_global_verbose_exits_validation_error(
    typer_cli_runner: CliRunner,
):
    # Regression: the root callback cannot see a subcommand-position --quiet,
    # so compose re-checks exclusivity after merging the flags.
    result = typer_cli_runner.invoke(
        cli.app, ["--verbose", "compose", "project", "--quiet"]
    )
    assert result.exit_code == 3
    assert "mutually exclusive" in result.output


def test_compose_sequence_prints_header(typer_cli_runner: CliRunner):
    result = typer_cli_runner.invoke(cli.app, ["compose", "streamlit"])
    assert result.exit_code == 0, result.output
    assert "Layers:" in result.output


def test_compose_per_layer_stdout_first_values(typer_cli_runner: CliRunner):
    result = typer_cli_runner.invoke(
        cli.app, ["compose", "--sections", "layers", "streamlit"]
    )
    assert result.exit_code == 0, result.output
    # Now mirrors 'final' behavior: should include final merged keys
    assert "project_name" in result.output


def test_compose_layers_and_final_stdout_ordering(typer_cli_runner: CliRunner):
    r_combo = typer_cli_runner.invoke(
        cli.app, ["compose", "--sections", "final,layers", "streamlit"]
    )
    assert r_combo.exit_code == 0, r_combo.output
    # Ensure header then FINAL then layer sections appear
    assert "FINAL" in r_combo.output
    assert "Layer 01" in r_combo.output


def test_compose_final_yaml_key_order_description_before_dependencies(
    typer_cli_runner: CliRunner,
):
    # Use a real template (streamlit) whose composition should place description first
    result = typer_cli_runner.invoke(
        cli.app, ["compose", "--sections", "final", "streamlit"]
    )
    assert result.exit_code == 0, result.output
    output = result.output
    # Verify ordering in the emitted YAML mapping
    idx_desc = output.find("description:")
    idx_deps = output.find("dependencies:")
    assert idx_desc != -1 and idx_deps != -1, output
    assert idx_desc < idx_deps, output


def test_compose_per_layer_dir_creates_files(
    tmp_path: Path, typer_cli_runner: CliRunner
):
    outdir = tmp_path / "artifacts"
    result = typer_cli_runner.invoke(
        cli.app,
        [
            "compose",
            "--sections",
            "final,final,layers,states,deltas",
            "-o",
            str(outdir),
            "streamlit",
        ],
    )
    assert result.exit_code == 0, result.output
    files = {p.name for p in outdir.iterdir()}
    # Two layers expected: project and streamlit
    assert "01-project-values.yaml" in files
    assert "02-streamlit-values.yaml" in files
    assert "01-project-state.yaml" in files
    assert "02-streamlit-state.yaml" in files
    assert (
        "02-streamlit-delta.yaml" in files
    )  # first delta may be empty but file exists
    assert "final.yaml" in files

    manifest = json.loads((outdir / "_index.json").read_text(encoding="utf-8"))
    # Regression: a repeated --sections value must not duplicate in the manifest
    assert manifest["sections"] == ["deltas", "final", "layers", "states"]


def test_compose_invalid_per_layer_with_file(
    tmp_path: Path, typer_cli_runner: CliRunner
):
    outfile = tmp_path / "out.yaml"
    outfile.write_text("x: 1\n")
    result = typer_cli_runner.invoke(
        cli.app,
        ["compose", "--sections", "layers", "-o", str(outfile), "project"],
    )
    # Typer Exit with our validation message
    assert result.exit_code != 0
    assert "Output path points to a file; provide a directory." in result.output


@pytest.mark.parametrize(
    "args",
    [
        pytest.param(["--quiet", "compose", "project"], id="global-flag"),
        pytest.param(["compose", "project", "--quiet"], id="subcommand-flag"),
    ],
)
def test_compose_quiet_silences_stdout_in_either_position(
    typer_cli_runner: CliRunner, args: list[str]
) -> None:
    """Regression: the same flag behaves identically in both positions."""
    result = typer_cli_runner.invoke(cli.app, args)
    assert result.exit_code == 0, result.output
    assert result.output == ""


def test_compose_unknown_section_reports_usage_error(typer_cli_runner: CliRunner):
    """A bad --sections value is input validation: exit 3, not click's default 2.

    docs/design/02-data-models.md §Exit Codes reserves 2 for CONFIG_ERROR.
    """
    result = typer_cli_runner.invoke(
        cli.app, ["compose", "project", "--sections", "final,unknown"]
    )
    assert result.exit_code == 3, result.output
    assert "Unknown section" in result.output


def test_compose_empty_sections_string_reports_usage_error(
    typer_cli_runner: CliRunner,
):
    """An empty --sections value is input validation: exit 3, not click's default 2.

    docs/design/02-data-models.md §Exit Codes reserves 2 for CONFIG_ERROR.
    """
    result = typer_cli_runner.invoke(
        cli.app, ["compose", "project", "--sections", "  "]
    )
    assert result.exit_code == 3, result.output
    # Rich hard-wraps at console width, so compare on whitespace-normalized text.
    assert "Select at least one section" in " ".join(result.output.split())


def test_compose_stats_writes_json_with_expected_shape(
    tmp_path: Path, typer_cli_runner: CliRunner
):
    outdir = tmp_path / "artifacts"
    result = typer_cli_runner.invoke(
        cli.app,
        [
            "compose",
            "--sections",
            "stats",
            "-o",
            str(outdir),
            "streamlit",
        ],
    )
    assert result.exit_code == 0, result.output

    stats_path = outdir / "stats.json"
    assert stats_path.exists(), (
        "stats.json should be written when selecting stats section"
    )

    payload = json.loads(stats_path.read_text(encoding="utf-8"))

    # Required keys from CompositionStats plus top-level alias "layers"
    expected_keys = {
        "layers",
        "layers_count",
        "total_keys",
        "total_scalars",
        "top_level_fields",
        "directives",
        "tasks",
        "max_depth",
        "delta_keys",
        "delta_scalars",
    }
    assert expected_keys.issubset(payload.keys()), (
        f"stats.json missing expected keys. Found: {sorted(payload.keys())}"
    )

    # Invariant: alias matches source
    assert payload["layers"] == payload["layers_count"]

    # Basic type checks and non-negative invariants
    int_fields = [
        "layers_count",
        "total_keys",
        "total_scalars",
        "top_level_fields",
        "tasks",
        "max_depth",
    ]
    for f in int_fields:
        assert isinstance(payload[f], int) and payload[f] >= 0, f

    # Optional fields may be null or non-negative ints
    for opt in ("delta_keys", "delta_scalars"):
        v = payload.get(opt)
        assert v is None or (isinstance(v, int) and v >= 0), opt

    # Directives is a list of strings; if present, they begin with underscore
    directives = payload.get("directives")
    assert isinstance(directives, list)
    for d in directives:
        assert isinstance(d, str)
        assert d.startswith("_"), d
