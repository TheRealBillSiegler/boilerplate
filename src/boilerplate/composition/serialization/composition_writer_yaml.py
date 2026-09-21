"""Deterministic YAML writer utilities (engine-independent)."""

from pathlib import Path

import yaml

from boilerplate.composition.models.json_types import JSON


class _IndentedSafeDumper(yaml.SafeDumper):
    """Safe dumper that indents block sequences under mapping keys."""

    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:
        _ = indentless
        return super().increase_indent(flow, False)


def dump_yaml(data: dict[str, JSON]) -> str:
    """Serialize a mapping to deterministic YAML text with a trailing newline."""
    text = yaml.dump(
        data,
        Dumper=_IndentedSafeDumper,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        indent=2,
        width=4096,
    )
    return text if text.endswith("\n") else text + "\n"


def write_yaml(data: dict[str, JSON], path: Path) -> None:
    """Write deterministic YAML to ``path`` using UTF-8 and LF newlines."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_yaml(data), encoding="utf-8", newline="\n")


__all__ = ["dump_yaml", "write_yaml"]
