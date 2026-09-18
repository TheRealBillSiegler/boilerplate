"""Validates that a template directory is well-formed.

Checks:
1. boilerplate.yml exists and is valid YAML (hardened loader)
2. copier.yml exists and is loadable by Copier's own config loader
3. copier.yml has no duplicate mapping keys (structural, tag-agnostic)
4. boilerplate.yml satisfies the TemplateMeta schema, version included
5. boilerplate.yml contains no custom YAML tags
6. Composition-intended templates (``_answers_file`` or ``extends``
   declared) ship their answers-file stub (warning only)
"""

import json
import re
from logging import getLogger
from pathlib import Path
from typing import NamedTuple

import typer
import yaml
from pydantic import ValidationError
from pydantic_core import ErrorDetails
from typer import Context
from yaml.nodes import MappingNode, Node, ScalarNode

from boilerplate.cli.types import TextFormat
from boilerplate.cli.utils import cli_error_handler
from boilerplate.common.yaml_loading import load_yaml
from boilerplate.constants import ExitCode
from boilerplate.integrations.copier_types import load_template_config
from boilerplate.models.template_meta import TemplateMeta

_logger = getLogger(__name__)

_STATUS_PASS = "PASS"
_STATUS_WARN = "WARN"
_STATUS_FAIL = "FAIL"

_SCHEMA_CHECK = "boilerplate.yml schema"
_VERSION_CHECK = "version format"


class _CheckResult:
    """Result of a single validation check."""

    def __init__(self, name: str, status: str, message: str = "") -> None:
        self.name = name
        self.status = status
        self.message = message

    def to_dict(self) -> dict[str, str]:
        """Converts to JSON-serializable dict."""
        result: dict[str, str] = {"name": self.name, "status": self.status}
        if self.message:
            result["message"] = self.message
        return result


def _check_file_exists(template_dir: Path, filename: str) -> _CheckResult:
    """Checks that a required file exists."""
    path = template_dir / filename
    if path.is_file():
        return _CheckResult(f"{filename} exists", _STATUS_PASS)
    return _CheckResult(
        f"{filename} exists",
        _STATUS_FAIL,
        f"{filename} not found in {template_dir}",
    )


class _MetaFile(NamedTuple):
    """boilerplate.yml read and parsed once, shared by every check that needs it.

    Attributes:
        text: Raw file contents; ``None`` when the file is absent.
        data: Parsed document; ``None`` when absent or unparseable.
        error: YAML parse error message, if parsing failed.
    """

    text: str | None
    data: object
    error: str | None


def _read_meta(template_dir: Path) -> _MetaFile:
    """Reads and parses boilerplate.yml once for the checks that inspect it.

    Args:
        template_dir: Template directory being validated.

    Returns:
        The file's text, parsed document, and parse error.
    """
    path = template_dir / "boilerplate.yml"
    if not path.is_file():
        return _MetaFile(None, None, None)
    text = path.read_text(encoding="utf-8")
    try:
        return _MetaFile(text, load_yaml(text), None)
    except yaml.YAMLError as e:
        return _MetaFile(text, None, str(e))


def _check_yaml_valid(meta: _MetaFile) -> _CheckResult:
    """Checks that boilerplate.yml is valid YAML."""
    name = "boilerplate.yml valid YAML"
    if meta.text is None:
        return _CheckResult(name, _STATUS_FAIL, "File not found")
    if meta.error is not None:
        return _CheckResult(name, _STATUS_FAIL, meta.error)
    return _CheckResult(name, _STATUS_PASS)


def _check_copier_yml_loadable(template_dir: Path) -> _CheckResult:
    """Checks that copier.yml loads with Copier's own config loader.

    copier.yml parsing is delegated to Copier per
    docs/design/03-template-system.md (YAML Parsing Rules), so Copier-native
    constructs such as the ``!include`` tag and multi-document files are
    valid. Only configuration is loaded; ``_tasks``/``_migrations`` entries
    are read as plain data and never executed.
    """
    name = "copier.yml loadable by Copier"
    path = template_dir / "copier.yml"
    if not path.is_file():
        return _CheckResult(name, _STATUS_FAIL, "File not found")
    try:
        # quiet=True keeps Copier from printing the traceback itself; the
        # chained cause carries the useful parser message for the FAIL line.
        load_template_config(path, quiet=True)
    except (yaml.YAMLError, ValueError, OSError) as e:
        return _CheckResult(name, _STATUS_FAIL, str(e.__cause__ or e))
    return _CheckResult(name, _STATUS_PASS)


def _check_no_duplicate_keys(template_dir: Path, filename: str) -> _CheckResult:
    """Checks for duplicate mapping keys without constructing any tags.

    Works at the YAML node level (``yaml.compose_all``), so Copier-native
    tags such as ``!include`` cannot break it -- no constructor ever runs.
    Covers every document in a multi-document file. Merge keys (``<<``) are
    exempt: YAML permits repeating them at one level.
    """
    name = f"{filename} no duplicate keys"
    path = template_dir / filename
    if not path.is_file():
        return _CheckResult(name, _STATUS_PASS)
    merge_tag = "tag:yaml.org,2002:merge"
    try:
        with path.open(encoding="utf-8") as f:
            stack: list[Node] = [
                doc for doc in yaml.compose_all(f, yaml.SafeLoader) if doc is not None
            ]
    except yaml.YAMLError as e:
        return _CheckResult(name, _STATUS_FAIL, str(e))
    while stack:
        node = stack.pop()
        if not isinstance(node, MappingNode):
            if isinstance(node.value, list):
                stack.extend(n for n in node.value if isinstance(n, Node))
            continue
        seen: set[tuple[str, str]] = set()
        for key_node, value_node in node.value:
            if isinstance(key_node, ScalarNode) and key_node.tag != merge_tag:
                key = (key_node.tag, key_node.value)
                if key in seen:
                    line = key_node.start_mark.line + 1
                    return _CheckResult(
                        name,
                        _STATUS_FAIL,
                        f"duplicate key {key_node.value!r} on line {line}",
                    )
                seen.add(key)
            stack.append(key_node)
            stack.append(value_node)
    return _CheckResult(name, _STATUS_PASS)


def _describe(error: ErrorDetails) -> str:
    """Renders one pydantic error as ``field: message``."""
    field = ".".join(str(part) for part in error["loc"])
    return f"{field}: {error['msg']}" if field else error["msg"]


def _summarize(name: str, messages: list[str]) -> _CheckResult:
    """Turns the messages attributed to one check into its result."""
    if messages:
        return _CheckResult(name, _STATUS_FAIL, "; ".join(messages))
    return _CheckResult(name, _STATUS_PASS)


def _check_meta_schema(meta: _MetaFile) -> list[_CheckResult]:
    """Validates boilerplate.yml against TemplateMeta and splits the failures.

    TemplateMeta owns the boilerplate.yml schema, so validating through it
    keeps ``validate`` accepting exactly the metadata that discovery and
    rendering accept. Version failures are reported under their own check
    name per docs/design/05-cli-reference.md (`validate` check registry).

    Args:
        meta: boilerplate.yml as read once.

    Returns:
        The schema check and the version check.
    """
    if meta.text is None:
        reason = "boilerplate.yml not found"
    elif meta.error is not None:
        reason = "Invalid YAML"
    elif not isinstance(meta.data, dict):
        reason = "boilerplate.yml is not a mapping"
    else:
        reason = None
    if reason is not None:
        return [
            _CheckResult(_SCHEMA_CHECK, _STATUS_FAIL, reason),
            _CheckResult(_VERSION_CHECK, _STATUS_FAIL, reason),
        ]

    errors: list[ErrorDetails] = []
    try:
        TemplateMeta.model_validate(meta.data)
    except ValidationError as e:
        errors = list(e.errors())

    return [
        _summarize(
            _SCHEMA_CHECK,
            [_describe(e) for e in errors if e["loc"][:1] != ("version",)],
        ),
        _summarize(
            _VERSION_CHECK,
            [_describe(e) for e in errors if e["loc"][:1] == ("version",)],
        ),
    ]


def _check_no_custom_yaml_tags(meta: _MetaFile) -> _CheckResult:
    """Checks that boilerplate.yml contains no custom YAML tags.

    The no-custom-tags security constraint is scoped to Boilerplate-owned
    files per docs/design/03-template-system.md (YAML Parsing Rules);
    copier.yml parsing is delegated to Copier, whose native tags (e.g.
    ``!include``) are legitimate.
    """
    name = "boilerplate.yml no custom tags"
    if meta.text is None:
        return _CheckResult(name, _STATUS_PASS)
    if "!!" in meta.text:
        return _CheckResult(
            name,
            _STATUS_WARN,
            "Custom YAML tags detected (!! syntax) in a Boilerplate-owned"
            " file. May be a security concern.",
        )
    return _CheckResult(name, _STATUS_PASS)


_ANSWERS_FILE_STUB_CHECK = "answers-file stub present"
_ANSWERS_FILE_STUB_NAME_PATTERN = re.compile(r"\s+")
_ANSWERS_FILE_STUB_NORMALIZED_NAME = "{{_copier_conf.answers_file}}.jinja"


def _check_answers_file_stub(template_dir: Path, meta: _MetaFile) -> _CheckResult:
    """Warn when a composition-intended template lacks its answers-file stub.

    Declaring ``_answers_file`` in copier.yml or a non-empty ``extends`` in
    boilerplate.yml signals a template meant to compose. Per
    docs/design/04-composition-engine.md (`_answers_file:` directive and
    answers-file stub), the directive alone is inert -- Copier writes an
    answers file only by rendering the stub template literally named
    ``{{ _copier_conf.answers_file }}.jinja``; a layer missing it composes
    cleanly but silently produces no answers file.
    """
    name = _ANSWERS_FILE_STUB_CHECK
    copier_path = template_dir / "copier.yml"
    if not copier_path.is_file():
        return _CheckResult(name, _STATUS_PASS)
    try:
        config = load_template_config(copier_path, quiet=True)
    except (yaml.YAMLError, ValueError, OSError):
        # Reported by "copier.yml loadable by Copier" already.
        return _CheckResult(name, _STATUS_PASS)

    declares_answers_file = "_answers_file" in config
    declares_extends = isinstance(meta.data, dict) and bool(meta.data.get("extends"))
    if not (declares_answers_file or declares_extends):
        return _CheckResult(name, _STATUS_PASS)

    has_stub = any(
        f.is_file()
        and _ANSWERS_FILE_STUB_NAME_PATTERN.sub("", f.name)
        == _ANSWERS_FILE_STUB_NORMALIZED_NAME
        for f in template_dir.iterdir()
    )
    if has_stub:
        return _CheckResult(name, _STATUS_PASS)
    return _CheckResult(
        name,
        _STATUS_WARN,
        "Template declares _answers_file or extends but ships no"
        " {{ _copier_conf.answers_file }}.jinja stub -- composition will"
        " succeed and silently write no answers file for this layer.",
    )


TEMPLATE_DIR_ARG = typer.Argument(
    ..., help="Path to the template directory to validate."
)
FORMAT_OPTION = typer.Option(TextFormat.TEXT, "--format", help="Output format.")
STRICT_OPTION = typer.Option(False, "--strict", help="Treat warnings as errors.")


@cli_error_handler
def validate(
    ctx: Context,
    template_dir: Path = TEMPLATE_DIR_ARG,
    format: TextFormat = FORMAT_OPTION,
    strict: bool = STRICT_OPTION,
) -> None:
    """Validates that a template directory is well-formed."""
    cli_context = ctx.obj
    display = cli_context.display

    if not template_dir.is_dir():
        display.error(f"Not a directory: {template_dir}")
        raise typer.Exit(code=ExitCode.VALIDATION_ERROR)

    meta = _read_meta(template_dir)
    checks: list[_CheckResult] = [
        _check_file_exists(template_dir, "boilerplate.yml"),
        _check_file_exists(template_dir, "copier.yml"),
        _check_yaml_valid(meta),
        _check_copier_yml_loadable(template_dir),
        _check_no_duplicate_keys(template_dir, "copier.yml"),
        *_check_meta_schema(meta),
        _check_no_custom_yaml_tags(meta),
        _check_answers_file_stub(template_dir, meta),
    ]

    passed = sum(1 for c in checks if c.status == _STATUS_PASS)
    warnings = sum(1 for c in checks if c.status == _STATUS_WARN)
    errors = sum(1 for c in checks if c.status == _STATUS_FAIL)

    if format is TextFormat.JSON:
        display.write(
            json.dumps(
                {
                    "checks": [c.to_dict() for c in checks],
                    "summary": {
                        "passed": passed,
                        "warnings": warnings,
                        "errors": errors,
                    },
                }
            )
        )
    else:
        for check in checks:
            if check.status == _STATUS_PASS:
                display.success(f"{_STATUS_PASS}  {check.name}")
            elif check.status == _STATUS_WARN:
                display.warning(f"{_STATUS_WARN}  {check.name}")
                if check.message:
                    display.write(f"       -> {check.message}")
            else:
                display.error(f"{_STATUS_FAIL}  {check.name}")
                if check.message:
                    display.write(f"       -> {check.message}")

        display.write("")
        display.info(
            f"{len(checks)} checks: {passed} passed, {warnings} warning(s), {errors} error(s)"
        )

    has_errors = errors > 0 or (strict and warnings > 0)
    if has_errors:
        raise typer.Exit(code=ExitCode.FAILURE)

    _logger.debug("Validate command completed: %d checks", len(checks))


__all__ = ["validate"]
