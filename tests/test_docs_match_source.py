"""Compare documentation claims against the source they describe.

Each test class targets one documented claim: a prompt count, an environment
variable table, a required-field table, or a `# Spec:` pointer. A test fails
when the doc and the source it describes disagree, and passes once the doc
is corrected to match the source. The source side is read from the
`boilerplate` package as it was actually imported, not from this checkout's
`src/` directory, so a package substituted ahead of it on `PYTHONPATH` is
what the docs get checked against.
"""

import re
import tomllib
from pathlib import Path
from typing import Final

import yaml

import boilerplate
from boilerplate.models.template_meta import TemplateMeta
from boilerplate.settings.settings import Settings

REPO_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
SRC_ROOT: Final[Path] = Path(str(boilerplate.__file__)).resolve().parent

# Forced to utf-8 while a template renders and restored afterward; not a setting.
_ENV_ALLOWLIST: Final[frozenset[str]] = frozenset({"PYTHONIOENCODING"})

_ENV_HELPER_NAME: Final[str] = "env_flag"

_ENV_LITERAL_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r'os\.environ\.get\(\s*["\']([A-Za-z_][A-Za-z0-9_]*)["\']'),
    re.compile(r'os\.environ\[\s*["\']([A-Za-z_][A-Za-z0-9_]*)["\']\s*\]'),
    re.compile(r'os\.getenv\(\s*["\']([A-Za-z_][A-Za-z0-9_]*)["\']'),
    re.compile(rf'\b{_ENV_HELPER_NAME}\(\s*["\']([A-Za-z_][A-Za-z0-9_]*)["\']'),
    # The containment form: "NAME" in os.environ / "NAME" not in os.environ.
    re.compile(r'["\']([A-Za-z_][A-Za-z0-9_]*)["\']\s+(?:not\s+)?in\s+os\.environ\b'),
)

_SPEC_POINTER_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^\s*# Spec: (?P<path>\S+?)(?: §(?P<section>.+))?\s*$"
)
_HEADING_PATTERN: Final[re.Pattern[str]] = re.compile(r"^#{1,6} (?P<text>.+)$")
_TRAILING_QUALIFIER_PATTERN: Final[re.Pattern[str]] = re.compile(r"\s*\([^()]*\)$")


def _iter_source_files() -> list[Path]:
    """Return every `.py` file under `src/boilerplate`, sorted for stable output."""
    return sorted(SRC_ROOT.rglob("*.py"))


def _settings_env_names() -> set[str]:
    """Return every environment variable name `Settings` reads via its prefix."""
    prefix = Settings.model_config.get("env_prefix", "")
    return {f"{prefix}{name}".upper() for name in Settings.model_fields}


class TestQuickstartPromptCount:
    def test_quickstart_prompt_count_matches_project_template(self) -> None:
        quickstart_text = (REPO_ROOT / "docs" / "quickstart.md").read_text(
            encoding="utf-8"
        )
        match = re.search(r"answer the (\d+) prompts", quickstart_text)
        assert match is not None, (
            "docs/quickstart.md no longer says 'answer the N prompts'"
        )
        documented_count = int(match.group(1))

        copier_config = yaml.safe_load(
            (SRC_ROOT / "templates" / "project" / "copier.yml").read_text(
                encoding="utf-8"
            )
        )
        assert isinstance(copier_config, dict)

        # Mirrors Copier's own filter_config: every non-underscore key is a
        # question (simplified `key: default` form included), unless it is
        # explicitly disabled with `when: false`.
        actual_count = sum(
            1
            for key, value in copier_config.items()
            if not key.startswith("_")
            and (not isinstance(value, dict) or value.get("when") is not False)
        )

        assert documented_count == actual_count, (
            f"docs/quickstart.md says {documented_count} prompts, but "
            f"src/boilerplate/templates/project/copier.yml asks {actual_count}"
        )


class TestCliEnvironmentTable:
    def test_env_table_lists_every_environ_read(self) -> None:
        scanned: set[str] = set()
        for source_file in _iter_source_files():
            text = source_file.read_text(encoding="utf-8")
            for pattern in _ENV_LITERAL_PATTERNS:
                scanned.update(pattern.findall(text))
        scanned.update(_settings_env_names())
        scanned -= _ENV_ALLOWLIST

        cli_md_text = (REPO_ROOT / "docs" / "cli.md").read_text(encoding="utf-8")
        section_start = cli_md_text.index("## Environment variables")
        next_heading = cli_md_text.find("\n## ", section_start + 1)
        section = cli_md_text[
            section_start : next_heading if next_heading != -1 else len(cli_md_text)
        ]

        documented: set[str] = set()
        for line in section.splitlines():
            stripped = line.strip()
            if not stripped.startswith("|") or "---" in stripped:
                continue
            cells = stripped.split("|")
            if len(cells) < 2:
                continue
            documented.update(re.findall(r"`([A-Z][A-Z0-9_]*)`", cells[1]))

        missing = scanned - documented
        assert not missing, (
            f"docs/cli.md's Environment variables table is missing: {sorted(missing)}"
        )


class TestAuthoringFieldTable:
    def test_required_column_matches_template_meta(self) -> None:
        authoring_text = (
            REPO_ROOT / "docs" / "templates-hub" / "authoring.md"
        ).read_text(encoding="utf-8")
        lines = authoring_text.splitlines()

        header_index = next(
            i
            for i, line in enumerate(lines)
            if re.match(r"\|\s*Field\s*\|\s*Required\s*\|\s*Description\s*\|", line)
        )

        rows: list[tuple[str, str]] = []
        for line in lines[header_index + 1 :]:
            stripped = line.strip()
            if not stripped.startswith("|"):
                break
            if "---" in stripped:
                continue
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            name_match = re.match(r"`([A-Za-z0-9_]+)`", cells[0])
            if name_match is None:
                continue
            rows.append((name_match.group(1), cells[1]))

        assert rows, "docs/templates-hub/authoring.md's Field table has no data rows"

        mismatches: list[str] = []
        for name, required_cell in rows:
            field = TemplateMeta.model_fields.get(name)
            assert field is not None, f"TemplateMeta has no field named {name!r}"
            documented_required = required_cell == "Yes"
            if field.is_required() != documented_required:
                mismatches.append(
                    f"{name}: table says Required={required_cell!r}, "
                    f"TemplateMeta.model_fields[{name!r}].is_required()="
                    f"{field.is_required()}"
                )

        assert not mismatches, "\n".join(mismatches)


class TestPytestMarkersTable:
    def test_registered_markers_match_agents_md_table(self) -> None:
        pyproject = tomllib.loads(
            (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )
        registered = pyproject["tool"]["pytest"]["ini_options"]["markers"]
        registered_names = {entry.split(":", 1)[0].strip() for entry in registered}

        agents_text = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        section_start = agents_text.index("### Markers")
        next_heading = agents_text.find("\n### ", section_start + 1)
        section = agents_text[
            section_start : next_heading if next_heading != -1 else len(agents_text)
        ]
        documented_names = set(re.findall(r"^\| `([a-z]+)`", section, re.MULTILINE))

        assert registered_names == documented_names, (
            f"pyproject.toml registers {sorted(registered_names)}, but AGENTS.md's "
            f"Markers table documents {sorted(documented_names)}"
        )

    def test_integration_marker_text_names_its_auto_apply_mechanism(self) -> None:
        pyproject = tomllib.loads(
            (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )
        registered = pyproject["tool"]["pytest"]["ini_options"]["markers"]
        integration_entry = next(
            entry
            for entry in registered
            if entry.split(":", 1)[0].strip() == "integration"
        )

        assert "auto" in integration_entry.lower(), (
            "pyproject.toml's 'integration' marker registration text should name "
            "the auto-apply mechanism (AGENTS.md's Markers table: 'Auto-applied to "
            "tests under tests/integration/ (conftest hook)'), not only how to "
            f"deselect it manually. Got: {integration_entry!r}"
        )


class TestCiSetupVariableCount:
    def test_quick_start_variable_count_matches_settings_yml(self) -> None:
        setup_text = (REPO_ROOT / "ci" / "SETUP.md").read_text(encoding="utf-8")
        match = re.search(r"set the (\w+) variables", setup_text)
        assert match is not None, "ci/SETUP.md no longer says 'set the N variables'"
        number_words = {
            "four": 4,
            "five": 5,
            "six": 6,
            "seven": 7,
            "eight": 8,
        }
        word = match.group(1)
        assert word in number_words or word.isdigit(), (
            f"ci/SETUP.md count {word!r} is not a number this test reads"
        )
        documented_count = int(word) if word.isdigit() else number_words[word]

        settings = yaml.safe_load(
            (REPO_ROOT / "ci" / "settings.yml").read_text(encoding="utf-8")
        )
        actual_count = len(settings["variables"])

        assert documented_count == actual_count, (
            f"ci/SETUP.md says {match.group(1)} variables, but ci/settings.yml "
            f"has {actual_count}"
        )


class TestSpecPointers:
    def test_spec_comments_point_at_existing_headings(self) -> None:
        failures: list[str] = []

        for source_file in _iter_source_files():
            lines = source_file.read_text(encoding="utf-8").splitlines()
            for line_number, line in enumerate(lines, start=1):
                match = _SPEC_POINTER_PATTERN.match(line)
                if match is None:
                    continue

                # Relative to SRC_ROOT.parent, not REPO_ROOT: when another
                # package copy is imported (scripts/new_tests_go_red.py puts
                # the base commit's src/ first), the file is outside the repo.
                relative_source = source_file.relative_to(SRC_ROOT.parent).as_posix()
                target_path = REPO_ROOT / match.group("path")
                if not target_path.is_file():
                    failures.append(
                        f"{relative_source}:{line_number} points at "
                        f"{match.group('path')}, which does not exist"
                    )
                    continue

                section = match.group("section")
                if section is None:
                    continue

                target_text = target_path.read_text(encoding="utf-8")
                headings: set[str] = set()
                in_code_block = False
                for target_line in target_text.splitlines():
                    if target_line.startswith("```"):
                        in_code_block = not in_code_block
                        continue
                    if in_code_block:
                        continue
                    heading_match = _HEADING_PATTERN.match(target_line)
                    if heading_match is None:
                        continue
                    text = heading_match.group("text")
                    headings.add(text)
                    # A trailing parenthetical qualifies the heading; the
                    # section name is the text before it.
                    headings.add(_TRAILING_QUALIFIER_PATTERN.sub("", text))
                if section not in headings:
                    failures.append(
                        f"{relative_source}:{line_number} points at "
                        f"{match.group('path')} §{section}, which has no such heading"
                    )

        assert not failures, "\n".join(failures)
