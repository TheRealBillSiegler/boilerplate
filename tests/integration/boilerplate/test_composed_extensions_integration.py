"""End-to-end render of a composition whose child layer declares a Jinja extension.

The merged questionnaire is asked by the first layer's Worker, so a question
default that uses a filter from a *sibling* layer's ``_jinja_extensions``
only renders if the merged union reaches every layer's Worker. This exercises
the real Copier Worker (no fakes) through the CLI.
"""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from boilerplate.cli.cli import app

_EXTENSION_MODULE = '''
"""Test-only Jinja extension providing the `probefilter` filter."""

from jinja2.ext import Extension


class ProbeExtension(Extension):
    def __init__(self, environment):
        super().__init__(environment)
        environment.filters["probefilter"] = lambda v: f"probed-{v}"
'''


@pytest.fixture()
def extension_composition(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Two-layer composition: base without extensions, child declaring one.

    The child's question default uses the extension's filter, forcing the
    base layer's Worker (which asks the merged questionnaire) to need the
    union. Returns the templates directory.
    """
    ext_dir = tmp_path / "pypath"
    ext_dir.mkdir()
    (ext_dir / "probe_ext.py").write_text(_EXTENSION_MODULE, encoding="utf-8")
    monkeypatch.syspath_prepend(str(ext_dir))

    templates = tmp_path / "templates"
    base = templates / "probebase"
    child = templates / "probechild"
    base.mkdir(parents=True)
    child.mkdir(parents=True)

    (base / "boilerplate.yml").write_text(
        'schema_version: "1"\nname: probebase\nversion: 0.1.0\n'
        "description: base layer without extensions\n",
        encoding="utf-8",
    )
    (base / "copier.yml").write_text(
        "project_name:\n  type: str\n  default: demo\n", encoding="utf-8"
    )
    (base / "base.txt.jinja").write_text(
        "base file for {{ project_name }}\n", encoding="utf-8"
    )

    (child / "boilerplate.yml").write_text(
        'schema_version: "1"\nname: probechild\nversion: 0.1.0\n'
        "description: child layer declaring an extension\nextends:\n  - probebase\n",
        encoding="utf-8",
    )
    (child / "copier.yml").write_text(
        "_answers_file: .copier-answers.probechild.yml\n"
        "_jinja_extensions:\n  - probe_ext.ProbeExtension\n"
        'slug:\n  type: str\n  default: "{{ project_name | probefilter }}"\n',
        encoding="utf-8",
    )
    (child / "child.txt.jinja").write_text("child slug: {{ slug }}\n", encoding="utf-8")
    (child / "{{_copier_conf.answers_file}}.jinja").write_text(
        "# Changes here will be overwritten by Copier; NEVER EDIT MANUALLY\n"
        "{{ _copier_answers|to_nice_yaml -}}\n",
        encoding="utf-8",
    )
    return templates


class TestComposedExtensionRender:
    def test_sibling_extension_filter_renders_in_merged_default(
        self,
        extension_composition: Path,
        tmp_path: Path,
        typer_cli_runner: CliRunner,
    ) -> None:
        dest = tmp_path / "out"

        result = typer_cli_runner.invoke(
            app,
            [
                "new",
                "probechild",
                str(dest),
                "--templates-dir",
                str(extension_composition),
                "--non-interactive",
                "--data",
                "project_name=hello",
                "--no-tasks",
                "--force",
            ],
        )

        assert result.exit_code == 0, result.output
        assert (dest / "base.txt").read_text(encoding="utf-8").strip() == (
            "base file for hello"
        )
        assert (dest / "child.txt").read_text(encoding="utf-8").strip() == (
            "child slug: probed-hello"
        )

    def test_answers_file_records_requested_child_layer(
        self,
        extension_composition: Path,
        tmp_path: Path,
        typer_cli_runner: CliRunner,
    ) -> None:
        dest = tmp_path / "out"

        result = typer_cli_runner.invoke(
            app,
            [
                "new",
                "probechild",
                str(dest),
                "--templates-dir",
                str(extension_composition),
                "--non-interactive",
                "--data",
                "project_name=hello",
                "--no-tasks",
                "--force",
            ],
        )

        assert result.exit_code == 0, result.output
        answers = (dest / ".copier-answers.probechild.yml").read_text(encoding="utf-8")
        assert "probechild" in answers
        assert "slug: probed-hello" in answers
        assert not (dest / ".copier-answers.yml").exists()
