"""Tests for `boilerplate validate` command."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from boilerplate.cli import app

_BOILERPLATE_YML = """\
name: "demo"
version: "1.0.0"
description: "Demo template."
"""

_COPIER_YML = """\
project_name:
  type: str
"""


def _write_template(
    tmp_path: Path,
    copier_yml: str = _COPIER_YML,
    boilerplate_yml: str = _BOILERPLATE_YML,
) -> Path:
    (tmp_path / "boilerplate.yml").write_text(boilerplate_yml, encoding="utf-8")
    (tmp_path / "copier.yml").write_text(copier_yml, encoding="utf-8")
    return tmp_path


class TestHappyPath:
    def test_all_checks_pass(self, tmp_path: Path, typer_cli_runner: CliRunner) -> None:
        _write_template(tmp_path)

        result = typer_cli_runner.invoke(app, ["validate", str(tmp_path)])

        assert result.exit_code == 0
        assert "FAIL" not in result.output
        assert "copier.yml loadable by Copier" in result.output


class TestCopierYmlLoadable:
    """copier.yml parsing is delegated to Copier (design 03 YAML Parsing Rules)."""

    def test_include_tag_passes(
        self, tmp_path: Path, typer_cli_runner: CliRunner
    ) -> None:
        includes = tmp_path / "includes"
        includes.mkdir()
        (includes / "questions.yml").write_text("q1:\n  type: str\n", encoding="utf-8")
        _write_template(tmp_path, copier_yml='!include "includes/*.yml"\n')

        result = typer_cli_runner.invoke(app, ["validate", str(tmp_path)])

        assert result.exit_code == 0
        assert "FAIL" not in result.output

    def test_multi_document_passes(
        self, tmp_path: Path, typer_cli_runner: CliRunner
    ) -> None:
        _write_template(
            tmp_path,
            copier_yml="q1:\n  type: str\n---\nq2:\n  type: int\n",
        )

        result = typer_cli_runner.invoke(app, ["validate", str(tmp_path)])

        assert result.exit_code == 0
        assert "FAIL" not in result.output

    def test_parse_failure_fails_with_copier_message(
        self, tmp_path: Path, typer_cli_runner: CliRunner
    ) -> None:
        _write_template(tmp_path, copier_yml="q1: [unclosed\n")

        result = typer_cli_runner.invoke(app, ["validate", str(tmp_path)])

        assert result.exit_code == 1
        assert "copier.yml loadable by Copier" in result.output
        assert "FAIL" in result.output


class TestCopierYmlDuplicateKeys:
    @pytest.mark.parametrize(
        "copier_yml",
        [
            pytest.param("q1:\n  type: str\nq1:\n  type: int\n", id="top-level"),
            pytest.param("q1:\n  type: str\n  type: int\n", id="nested"),
        ],
    )
    def test_duplicate_keys_fail(
        self, tmp_path: Path, typer_cli_runner: CliRunner, copier_yml: str
    ) -> None:
        _write_template(tmp_path, copier_yml=copier_yml)

        result = typer_cli_runner.invoke(app, ["validate", str(tmp_path)])

        assert result.exit_code == 1
        assert "duplicate key" in result.output

    def test_native_tags_do_not_break_the_check(
        self, tmp_path: Path, typer_cli_runner: CliRunner
    ) -> None:
        """The duplicate-key scan is structural: no tag is ever constructed."""
        includes = tmp_path / "includes"
        includes.mkdir()
        (includes / "questions.yml").write_text("q1:\n  type: str\n", encoding="utf-8")
        _write_template(
            tmp_path,
            copier_yml='!include "includes/*.yml"\n---\nq2:\n  type: int\n',
        )

        result = typer_cli_runner.invoke(app, ["validate", str(tmp_path)])

        assert result.exit_code == 0
        assert "FAIL" not in result.output


class TestSchema:
    """The schema check delegates to TemplateMeta, the boilerplate.yml schema owner."""

    def test_missing_description_passes(
        self, tmp_path: Path, typer_cli_runner: CliRunner
    ) -> None:
        """TemplateMeta defaults description to "", so validate accepts its absence.

        Regression: validate hand-rolled its own required-field list and
        rejected metadata that discovery and rendering both accept.
        """
        _write_template(tmp_path, boilerplate_yml='name: "demo"\nversion: "1.0.0"\n')

        result = typer_cli_runner.invoke(app, ["validate", str(tmp_path)])

        assert result.exit_code == 0, result.output
        assert "FAIL" not in result.output

    def test_missing_name_fails(
        self, tmp_path: Path, typer_cli_runner: CliRunner
    ) -> None:
        _write_template(tmp_path, boilerplate_yml='version: "1.0.0"\n')

        result = typer_cli_runner.invoke(app, ["validate", str(tmp_path)])

        assert result.exit_code == 1
        assert "boilerplate.yml schema" in result.output
        assert "name" in result.output


class TestVersionFormat:
    """Version check matches the PEP 440 parse TemplateMeta.load applies."""

    @pytest.mark.parametrize(
        "version",
        [
            pytest.param("1", id="single-component"),
            pytest.param("1.0.0-beta", id="prerelease-normalized-by-packaging"),
        ],
    )
    def test_loader_accepted_versions_pass(
        self, tmp_path: Path, typer_cli_runner: CliRunner, version: str
    ) -> None:
        _write_template(
            tmp_path,
            boilerplate_yml=(
                f'name: "demo"\nversion: "{version}"\ndescription: "Demo template."\n'
            ),
        )

        result = typer_cli_runner.invoke(app, ["validate", str(tmp_path)])

        assert result.exit_code == 0
        assert "FAIL" not in result.output

    def test_loader_rejected_version_fails(
        self, tmp_path: Path, typer_cli_runner: CliRunner
    ) -> None:
        _write_template(
            tmp_path,
            boilerplate_yml=(
                'name: "demo"\nversion: "1.0.x"\ndescription: "Demo template."\n'
            ),
        )

        result = typer_cli_runner.invoke(app, ["validate", str(tmp_path)])

        assert result.exit_code == 1
        assert "version format" in result.output
        assert "Invalid version" in result.output

    def test_non_mapping_yaml_fails_without_crashing(
        self, tmp_path: Path, typer_cli_runner: CliRunner
    ) -> None:
        """Regression: a list-form boilerplate.yml fails the check, not aborting."""
        _write_template(tmp_path, boilerplate_yml="- just\n- a-list\n")

        result = typer_cli_runner.invoke(app, ["validate", str(tmp_path)])

        assert result.exit_code == 1
        assert "boilerplate.yml is not a mapping" in result.output


class TestAnswersFileStub:
    """Composition-intended templates without a stub warn (design 04)."""

    _STUB_NAME = "{{_copier_conf.answers_file}}.jinja"

    def test_answers_file_directive_without_stub_warns(
        self, tmp_path: Path, typer_cli_runner: CliRunner
    ) -> None:
        _write_template(
            tmp_path, copier_yml="_answers_file: .copier-answers.demo.yml\n"
        )

        result = typer_cli_runner.invoke(app, ["validate", str(tmp_path)])

        assert result.exit_code == 0
        assert "WARN" in result.output
        assert "answers-file stub present" in result.output

    def test_extends_without_stub_warns(
        self, tmp_path: Path, typer_cli_runner: CliRunner
    ) -> None:
        _write_template(
            tmp_path,
            boilerplate_yml=_BOILERPLATE_YML + "extends:\n  - project\n",
        )

        result = typer_cli_runner.invoke(app, ["validate", str(tmp_path)])

        assert result.exit_code == 0
        assert "WARN" in result.output
        assert "answers-file stub present" in result.output

    def test_answers_file_directive_with_stub_passes(
        self, tmp_path: Path, typer_cli_runner: CliRunner
    ) -> None:
        _write_template(
            tmp_path, copier_yml="_answers_file: .copier-answers.demo.yml\n"
        )
        (tmp_path / self._STUB_NAME).write_text(
            "{{ _copier_answers|to_nice_yaml }}\n", encoding="utf-8"
        )

        result = typer_cli_runner.invoke(app, ["validate", str(tmp_path)])

        assert result.exit_code == 0
        assert "WARN" not in result.output

    def test_non_composition_template_without_stub_passes(
        self, tmp_path: Path, typer_cli_runner: CliRunner
    ) -> None:
        _write_template(tmp_path)

        result = typer_cli_runner.invoke(app, ["validate", str(tmp_path)])

        assert result.exit_code == 0
        assert "WARN" not in result.output

    def test_strict_promotes_warning_to_failure(
        self, tmp_path: Path, typer_cli_runner: CliRunner
    ) -> None:
        _write_template(
            tmp_path, copier_yml="_answers_file: .copier-answers.demo.yml\n"
        )

        result = typer_cli_runner.invoke(app, ["validate", str(tmp_path), "--strict"])

        assert result.exit_code == 1


class TestBoilerplateYmlCustomTags:
    def test_custom_tag_fails(
        self, tmp_path: Path, typer_cli_runner: CliRunner
    ) -> None:
        _write_template(
            tmp_path,
            boilerplate_yml=(
                _BOILERPLATE_YML
                + 'payload: !!python/object/apply:os.system ["echo hi"]\n'
            ),
        )

        result = typer_cli_runner.invoke(app, ["validate", str(tmp_path)])

        assert result.exit_code == 1
        assert "boilerplate.yml no custom tags" in result.output
