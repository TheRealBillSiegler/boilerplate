"""A composition scoped to one layer: that layer and its ancestors only."""

from pathlib import Path

import pytest

from boilerplate.composition.tasks import normalize_tasks
from boilerplate.composition.views import build_layer_view, scope_composition
from tests.boilerplate.templates.conftest import compose


def _layer(
    root: Path, name: str, *, extends: tuple[str, ...] = (), copier_yml: str = ""
) -> None:
    """Write the template `name` under `root` with the given `copier.yml` body."""
    folder = root / name
    folder.mkdir(parents=True)
    listed = "".join(f"  - {parent}\n" for parent in extends)
    (folder / "boilerplate.yml").write_text(
        f'schema_version: "1.0"\nname: {name}\ndescription: x\nversion: "1.0.0"\n'
        f"extends:\n{listed}"
        if extends
        else f'schema_version: "1.0"\nname: {name}\ndescription: x\nversion: "1.0.0"\n'
        "extends: []\n",
        encoding="utf-8",
    )
    (folder / "copier.yml").write_text(copier_yml, encoding="utf-8")


def _diamond(root: Path) -> None:
    """Write `base`, its children `left` and `right`, and `top` extending both."""
    _layer(root, "base", copier_yml="base_q:\n  type: str\n  default: b\n")
    _layer(
        root,
        "left",
        extends=("base",),
        copier_yml="left_q:\n  type: str\n  default: l\n",
    )
    _layer(
        root,
        "right",
        extends=("base",),
        copier_yml="right_q:\n  type: str\n  default: r\n_tasks:\n  - echo right\n",
    )
    _layer(
        root,
        "top",
        extends=("left", "right"),
        copier_yml="top_q:\n  type: str\n  default: t\n",
    )


class TestScopeComposition:
    """The scoped composition is the composition rooted at the layer."""

    def test_keeps_the_layer_and_its_ancestors_in_topological_order(
        self, tmp_path: Path
    ) -> None:
        _diamond(tmp_path)

        scoped = scope_composition(compose("top", tmp_path), "left")

        assert [layer.name for layer in scoped.layers] == ["base", "left"]

    def test_questions_exclude_siblings_and_descendants(self, tmp_path: Path) -> None:
        _diamond(tmp_path)

        scoped = scope_composition(compose("top", tmp_path), "left")

        assert set(build_layer_view(scoped).questions) == {"base_q", "left_q"}

    def test_tasks_exclude_siblings(self, tmp_path: Path) -> None:
        _diamond(tmp_path)

        scoped = scope_composition(compose("top", tmp_path), "left")

        assert normalize_tasks(scoped.final) == []
        assert normalize_tasks(compose("top", tmp_path).final) == ["echo right"]

    def test_equals_composing_from_the_layer(self, tmp_path: Path) -> None:
        _diamond(tmp_path)

        scoped = scope_composition(compose("top", tmp_path), "right")

        assert scoped == compose("right", tmp_path)

    def test_the_final_layers_scope_is_the_whole_composition(
        self, tmp_path: Path
    ) -> None:
        _diamond(tmp_path)
        full = compose("top", tmp_path)

        assert scope_composition(full, "top") == full

    def test_a_layer_outside_the_composition_raises_key_error(
        self, tmp_path: Path
    ) -> None:
        _diamond(tmp_path)

        with pytest.raises(KeyError, match="elsewhere"):
            scope_composition(compose("top", tmp_path), "elsewhere")
