"""Bundled templates stay updatable layer by layer with vanilla ``copier update``.

Guards the two authoring rules the per-layer update story rests on
(docs/design/adr-015-idiomatic-artifacts.md, points 1 and 4), each learned from
a real defect on the shipped templates: a declared ``_exclude`` replaces
Copier's defaults, so a template that declares one must restate them or a
git-backed update copies the clone's ``.git`` over the project's; and a
per-layer update renders from that layer's own ``copier.yml`` alone, so every
answer a layer's files or paths use must be declared there, inherited or not.
"""

import re
from pathlib import Path

import pytest
import yaml

from boilerplate.integrations.copier_types import DEFAULT_EXCLUDE
from tests.boilerplate.templates.conftest import LAYERS

AUTHORING_METADATA = "/boilerplate.yml"
# Names Copier itself provides to every render.
COPIER_BUILTINS = {"_copier_answers", "_copier_conf", "_copier_python", "_folder_name"}
SKIPPED_PARTS = {".git", "__pycache__", "_extensions"}
AUTHORING_FILES = {"copier.yml", "boilerplate.yml"}


def _copier_config(layer: Path) -> dict[str, object]:
    return yaml.safe_load((layer / "copier.yml").read_text(encoding="utf-8"))


def _extends(layer: Path) -> bool:
    return bool(
        yaml.safe_load((layer / "boilerplate.yml").read_text(encoding="utf-8")).get(
            "extends"
        )
    )


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


class TestExtendingLayerDeclaresAnswersItsFilesUse:
    @pytest.mark.parametrize(
        "layer", [layer for layer in LAYERS if _extends(layer)], ids=lambda p: p.name
    )
    def test_every_name_used_is_a_question_of_this_layer(self, layer: Path) -> None:
        declared = {key for key in _copier_config(layer) if not key.startswith("_")}
        assert _names_used(layer) <= declared
