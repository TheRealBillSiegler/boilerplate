from collections.abc import Callable
from pathlib import Path

import pytest

from boilerplate.composition.composer import Composer
from boilerplate.composition.models import Composition
from boilerplate.composition.resolution.models.resolution import Resolution
from boilerplate.models.template_info import TemplateInfo


def test_compose_basic_with_factory(
    composition_factory: Callable[..., Composition],
):
    """Tests basic composition building using the composition factory."""
    template_specs = ["alpha@1.0.0", "beta@2.0.0"]
    layer_schemas = [
        {"p": "/tmp/path1", "a": 1},
        {"q": "/tmp/path2", "b": 2},
    ]
    final_schema = {"final": True, "_tasks": [["echo one"], ["echo two"]]}

    composition = composition_factory(template_specs, layer_schemas, final_schema)

    # Assert: sequence and graph
    assert composition.sequence == ["alpha@1.0.0", "beta@2.0.0"]
    assert list(composition.graph.nodes.keys()) == ["alpha@1.0.0", "beta@2.0.0"]

    # Assert: layers
    assert len(composition.layers) == 2
    assert composition.layers[0].name == "alpha"
    assert composition.layers[0].values["p"] == "/tmp/path1"
    assert isinstance(composition.layers[0].values["p"], str)
    assert composition.layers[1].values["b"] == 2

    # Assert: final schema carries tasks
    assert composition.final["final"] is True
    assert composition.final["_tasks"] == [["echo one"], ["echo two"]]


def test_compose_basic(template_factory: Callable[..., TemplateInfo]):
    # Arrange: two templates with simple layer schemas
    t1 = template_factory("alpha", "1.0.0")
    t2 = template_factory("beta", "2.0.0")

    # Act
    order = [f"{t1.name}@{t1.meta.version}", f"{t2.name}@{t2.meta.version}"]
    res = Resolution(
        deps={order[0]: [order[1]], order[1]: []},
        templates={order[0]: t1, order[1]: t2},
    )
    composition = Composer().compose(res)

    # Assert: sequence uses dependency ordering
    assert composition.sequence == [
        "beta@2.0.0",
        "alpha@1.0.0",
    ]  # beta is dependency of alpha
    assert list(composition.graph.nodes.keys()) == ["alpha@1.0.0", "beta@2.0.0"]

    # Assert: layers
    assert len(composition.layers) == 2
    assert composition.layers[0].name == "beta"  # dependency first
    assert composition.layers[1].name == "alpha"


def test_graph_edges_preserve_extends_declaration_order(
    template_factory: Callable[..., TemplateInfo],
):
    """Edge lists preserve extends declaration order rather than sorting it.

    Declaration order carries sibling-precedence semantics: a later-declared
    sibling renders later and wins file conflicts (design 04,
    diamond-dependencies section). Lexicographic sorting would misrepresent
    that precedence to any consumer reading edge order.
    """
    root = template_factory("root", "1.0.0")
    zeta = template_factory("zeta-lib", "1.0.0")
    alpha = template_factory("alpha-lib", "1.0.0")

    root_spec = f"{root.name}@{root.meta.version}"
    zeta_spec = f"{zeta.name}@{zeta.meta.version}"
    alpha_spec = f"{alpha.name}@{alpha.meta.version}"

    # root extends [zeta-lib, alpha-lib] in that declared order
    res = Resolution(
        deps={root_spec: [zeta_spec, alpha_spec], zeta_spec: [], alpha_spec: []},
        templates={root_spec: root, zeta_spec: zeta, alpha_spec: alpha},
    )
    composition = Composer().compose(res)

    assert composition.graph.edges[root_spec] == [zeta_spec, alpha_spec]


def test_compose_no_tasks_and_empty_configs(
    template_factory: Callable[..., TemplateInfo],
):
    # Arrange: three templates but empty configs
    t1 = template_factory("one", "0.1.0")
    t2 = template_factory("two", "0.2.0")
    t3 = template_factory("three", "0.3.0")

    # Act
    order = [
        f"{t1.name}@{t1.meta.version}",
        f"{t2.name}@{t2.meta.version}",
        f"{t3.name}@{t3.meta.version}",
    ]
    res = Resolution(
        deps={order[0]: [], order[1]: [], order[2]: []},
        templates={order[0]: t1, order[1]: t2, order[2]: t3},
    )

    # Use custom extract_config that returns empty configs to test
    # the "empty configs" scenario
    def extract_empty_config(_template_info: TemplateInfo) -> dict[str, object]:
        return {}

    composition = Composer(extract_config=extract_empty_config).compose(res)

    # Assert: sequence includes all three; independent roots tie-break
    # lexicographically (design 04 Stage 2)
    assert len(composition.layers) == 3
    assert composition.sequence == [
        "one@0.1.0",
        "three@0.3.0",
        "two@0.2.0",
    ]
    assert sorted(composition.graph.nodes.keys()) == sorted(composition.sequence)

    # Assert: values for empty configs default to {}
    assert composition.layers[0].values == {}
    assert composition.layers[1].values == {}
    assert composition.layers[2].values == {}

    # Assert: final schema has no _tasks when none provided
    assert "_tasks" not in composition.final


def test_compose_with_states_and_deltas(template_factory: Callable[..., TemplateInfo]):
    """Tests composition with state tracking and delta computation."""
    t1 = template_factory("alpha", "1.0.0")
    t2 = template_factory("beta", "2.0.0")

    order = [f"{t1.name}@{t1.meta.version}", f"{t2.name}@{t2.meta.version}"]
    res = Resolution(
        deps={order[0]: [], order[1]: []}, templates={order[0]: t1, order[1]: t2}
    )

    composition = Composer().compose(res, include_states=True, include_deltas=True)

    # Assert: states are captured
    assert all(layer.state_after is not None for layer in composition.layers)

    # Assert: deltas are captured (though may be empty for templates with no config)
    for layer in composition.layers:
        assert layer.delta is not None  # delta dict exists, even if empty


@pytest.mark.parametrize(
    "raw_values,expected",
    [
        ({"p": Path("/tmp/a")}, {"p": str(Path("/tmp/a"))}),
        (
            {"lst": [Path("/x"), 1, {"k": Path("/y")}]},
            {"lst": [str(Path("/x")), 1, {"k": str(Path("/y"))}]},
        ),
        ({"nested": {"inner": Path("/z")}}, {"nested": {"inner": str(Path("/z"))}}),
    ],
)
def test_composer_coerces_raw_paths_to_str(
    template_factory: Callable[..., TemplateInfo],
    raw_values: dict[str, object],
    expected: dict[str, object],
):
    """Composer coerces a raw ``pathlib.Path`` from ``extract_config`` to ``str``.

    ``extract_config`` hands the Composer real, un-normalized values (as a
    template's own config would); the composer's own ``ensure_json`` call is
    what turns the ``Path`` into a ``str``, not any conversion in this test.
    """
    t = template_factory("coerce", "1.0.0")

    def extract_config_with_raw_path(_template_info: TemplateInfo) -> dict[str, object]:
        return raw_values

    composer = Composer(extract_config=extract_config_with_raw_path)

    order = [f"{t.name}@{t.meta.version}"]
    res = Resolution(deps={order[0]: []}, templates={order[0]: t})
    composition = composer.compose(res)

    assert composition.layers[0].values == expected


def test_composer_raises_type_error_for_non_json_serializable_value(
    template_factory: Callable[..., TemplateInfo],
):
    """A value ``ensure_json`` cannot represent raises ``TypeError``.

    Matches the contract documented on
    ``boilerplate.composition.models.json_types.ensure_json``: an object of
    an unrecognized type is rejected, not silently dropped or stringified.
    Composer reaches this while building ``final`` (every layer's raw config
    is normalized via ``serialize_for_yaml``, itself built on ``ensure_json``)
    before it ever gets to a per-layer ``values`` coercion, so the failure
    surfaces on the very first offending layer regardless of position.
    """

    class Unserializable:
        """A plain object with no JSON-compatible representation."""

    t = template_factory("coerce", "1.0.0")

    def extract_config_with_bad_value(
        _template_info: TemplateInfo,
    ) -> dict[str, object]:
        return {"bad": Unserializable()}

    composer = Composer(extract_config=extract_config_with_bad_value)

    order = [f"{t.name}@{t.meta.version}"]
    res = Resolution(deps={order[0]: []}, templates={order[0]: t})

    with pytest.raises(TypeError, match="not JSON-serializable"):
        composer.compose(res)
