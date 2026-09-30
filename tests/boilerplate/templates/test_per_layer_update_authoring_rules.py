"""Bundled templates stay composable and updatable layer by layer.

Guards two authoring rules over every bundled layer, each learned from a real
defect on the shipped templates:

- A declared ``_exclude`` replaces Copier's defaults, so a template that
  declares one must restate them or a git-backed update copies the clone's
  ``.git`` over the project's (docs/design/adr-015-idiomatic-artifacts.md,
  point 1).
- Composition is Boilerplate's process, not a template property. A layer
  declares its own questions and the parent questions it overrides or
  extends, nothing more; every other answer its files and paths use reaches
  it through the merged schema (docs/design/04-composition-engine.md,
  Configuration Merger). A layer that restates a parent's question unchanged
  duplicates the schema by hand, which is the drift these tests exist to
  catch.

A third rule guards ``_skip_if_exists`` itself: a pattern naming no path the
layer renders can never protect anything and is dead authoring, most likely a
typo; this is a convention of the bundled layers, pinned here.
"""

import re
from pathlib import Path

import pytest
import yaml

from boilerplate.cli.utils import build_template_catalog
from boilerplate.composition import Composer
from boilerplate.composition.resolution import Resolver
from boilerplate.integrations.copier_types import DEFAULT_EXCLUDE
from boilerplate.settings import Settings
from tests.boilerplate.templates.conftest import LAYERS, TEMPLATES

AUTHORING_METADATA = "/boilerplate.yml"
# Names Copier itself provides to every render.
COPIER_BUILTINS = {"_copier_answers", "_copier_conf", "_copier_python", "_folder_name"}
SKIPPED_PARTS = {".git", "__pycache__", "_extensions"}
AUTHORING_FILES = {"copier.yml", "boilerplate.yml"}
DEFAULT_TEMPLATES_SUFFIX = ".jinja"


def _copier_config(layer: Path) -> dict[str, object]:
    return yaml.safe_load((layer / "copier.yml").read_text(encoding="utf-8"))


def _questions(layer: Path) -> dict[str, object]:
    return {k: v for k, v in _copier_config(layer).items() if not k.startswith("_")}


def _parents(layer: Path) -> list[Path]:
    meta = yaml.safe_load((layer / "boilerplate.yml").read_text(encoding="utf-8"))
    return [TEMPLATES / name for name in meta.get("extends") or []]


def _merged_questions(layer: Path) -> set[str]:
    """Question names the composition rooted at `layer` asks, per the merger."""
    registry = build_template_catalog(None, Settings())
    composition = Composer().compose(Resolver().resolve(layer.name, registry))
    return set(composition.merged_questions_schema)


def _leading_name(expression: str) -> set[str]:
    match = re.match(r"\s*\(?\s*(?:not\s+)?([A-Za-z_]\w*)", expression)
    return {match.group(1)} if match else set()


def _names_used(layer: Path) -> set[str]:
    """Names the layer's Jinja expressions (file contents and paths) lead with."""
    used: set[str] = set()
    bound: set[str] = set()
    for path in layer.rglob("*"):
        rel = path.relative_to(layer)
        if SKIPPED_PARTS & set(rel.parts) or rel.name in AUTHORING_FILES:
            continue
        sources = [rel.as_posix()]
        if path.is_file() and path.suffix == ".jinja":
            sources.append(path.read_text(encoding="utf-8"))
        for source in sources:
            for expression in re.findall(r"\{\{-?(.+?)-?\}\}", source, re.DOTALL):
                used |= _leading_name(expression)
            for expression in re.findall(
                r"\{%-?\s*(?:if|elif)\s+(.+?)-?%\}", source, re.DOTALL
            ):
                used |= _leading_name(expression)
            for names in re.findall(r"\{%-?\s*for\s+([\w, ]+?)\s+in\b", source):
                bound |= {name.strip() for name in names.split(",")}
            bound |= set(re.findall(r"\{%-?\s*set\s+(\w+)", source))
    return used - bound - COPIER_BUILTINS


EXTENDING_LAYERS = [layer for layer in LAYERS if _parents(layer)]


class TestExcludeRestatesCopierDefaults:
    @pytest.mark.parametrize("layer", LAYERS, ids=lambda p: p.name)
    def test_declared_exclude_carries_the_defaults_and_authoring_metadata(
        self, layer: Path
    ) -> None:
        exclude = _copier_config(layer).get("_exclude")
        assert isinstance(exclude, list), "every bundled layer declares _exclude"
        restated = {str(pattern).lstrip("/") for pattern in exclude}
        assert set(DEFAULT_EXCLUDE) <= restated
        assert AUTHORING_METADATA in exclude


class TestExtendingLayerRendersFromTheMergedSchema:
    @pytest.mark.parametrize("layer", EXTENDING_LAYERS, ids=lambda p: p.name)
    def test_every_name_used_is_a_question_of_the_composition(
        self, layer: Path
    ) -> None:
        assert _names_used(layer) <= _merged_questions(layer)


class TestExtendingLayerDeclaresOnlyWhatItOverrides:
    @pytest.mark.parametrize("layer", EXTENDING_LAYERS, ids=lambda p: p.name)
    def test_a_parent_question_is_redeclared_only_with_a_change(
        self, layer: Path
    ) -> None:
        own = _questions(layer)
        duplicated = sorted(
            name
            for parent in _parents(layer)
            for name, declaration in _questions(parent).items()
            if name in own and own[name] == declaration
        )
        assert not duplicated, (
            f"{layer.name} restates {', '.join(duplicated)} exactly as its parent "
            "declares them; a layer redeclares a parent's question only to "
            "override or extend it"
        )


def _normalize_path(path: str) -> str:
    """Collapse a Jinja expression in a path to a single wildcard.

    Args:
        path: A rendered-path candidate or a `_skip_if_exists` pattern,
            either of which may contain a `{{ ... }}` expression (e.g. the
            package directory).

    Returns:
        `path` with every `{{ ... }}` expression replaced by `*`, so a
        pattern and the rendered path it is meant to protect compare equal
        regardless of the answer the expression resolves to.
    """
    return re.sub(r"\{\{.*?\}\}", "*", path)


def _rendered_relpaths(layer: Path, templates_suffix: str) -> set[str]:
    """Return every path-normalized file `layer` renders, `.jinja` suffix stripped.

    Args:
        layer: The bundled layer directory.
        templates_suffix: The layer's own `_templates_suffix` (Copier default:
            `.jinja`).

    Returns:
        Normalized (see `_normalize_path`) relative paths, one per file the
        layer ships as template content.
    """
    paths: set[str] = set()
    for path in layer.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(layer)
        if SKIPPED_PARTS & set(rel.parts) or rel.name in AUTHORING_FILES:
            continue
        text = rel.as_posix().removesuffix(templates_suffix)
        paths.add(_normalize_path(text))
    return paths


class TestSkipIfExistsPatternsMatchRenderedPaths:
    @pytest.mark.parametrize("layer", LAYERS, ids=lambda p: p.name)
    def test_every_pattern_matches_a_path_this_layer_renders(self, layer: Path) -> None:
        """Every declared pattern is an exact path this layer renders.

        The rule for bundled layers: a `_skip_if_exists` entry names one
        rendered path exactly (package-name segments aside), never a glob or
        directory pattern — no bundled layer needs that, so this checks for
        an exact match only.
        """
        config = _copier_config(layer)
        raw_patterns = config.get("_skip_if_exists")
        patterns: list[object] = raw_patterns if isinstance(raw_patterns, list) else []
        templates_suffix = str(
            config.get("_templates_suffix") or DEFAULT_TEMPLATES_SUFFIX
        )
        rendered = _rendered_relpaths(layer, templates_suffix)
        for pattern in patterns:
            normalized = _normalize_path(str(pattern))
            assert normalized in rendered, (
                f"{pattern!r} in {layer.name}'s _skip_if_exists names no path "
                f"{layer.name} renders"
            )
