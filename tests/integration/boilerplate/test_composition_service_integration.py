from collections.abc import Callable

from boilerplate.catalog import TemplateCatalog
from boilerplate.composition import Composer
from boilerplate.composition.resolution import Resolver
from boilerplate.models.template_info import TemplateInfo


def test_resolver_builds_execution_sequence_correctly(
    template_factory: Callable[..., TemplateInfo],
) -> None:
    # Build A -> [B, C] with B -> D
    registry = TemplateCatalog()
    d = template_factory("d", "1.0.0")
    b = template_factory("b", "1.0.0", extends=["d"])  # unpinned
    c = template_factory("c", "1.0.0")
    a = template_factory("a", "1.0.0", extends=["b@1.0.0", "c"])  # mixed pins
    registry.register_many([a, b, c, d])

    resolution = Resolver().resolve("a@1.0.0", registry)
    execution_sequence = resolution.execution_sequence

    # Basic behavior assertions: returns all layers exactly once
    assert len(execution_sequence) == 4
    assert set(execution_sequence) == {"a@1.0.0", "b@1.0.0", "c@1.0.0", "d@1.0.0"}

    # Check we have all templates in resolution
    assert len(resolution.templates) == 4
    assert "a@1.0.0" in resolution.templates
    assert "b@1.0.0" in resolution.templates
    assert "c@1.0.0" in resolution.templates
    assert "d@1.0.0" in resolution.templates


def test_diamond_composition_conflicting_config_declaration_order_wins(
    template_factory: Callable[..., TemplateInfo],
) -> None:
    """True diamond, full -> [web, api] -> base, with web/api conflicting on a key.

    Regression for the bug where diamond conflicts were resolved by alphabetical
    name instead of ``extends`` declaration order (docs/design/04-composition-engine.md
    Stage 2 + Diamond section). ``full`` declares ``[web, api]`` so ``api`` (declared
    second) must win; ``full2`` below declares ``[api, web]`` and must flip the winner
    to ``web``, proving declaration order — not alphabetical name order — governs.
    """
    registry = TemplateCatalog()
    base = template_factory("base", "1.0.0")
    web = template_factory("web", "1.0.0", extends=["base@1.0.0"])
    api = template_factory("api", "1.0.0", extends=["base@1.0.0"])
    full = template_factory("full", "1.0.0", extends=["web@1.0.0", "api@1.0.0"])
    full2 = template_factory("full2", "1.0.0", extends=["api@1.0.0", "web@1.0.0"])
    registry.register_many([base, web, api, full, full2])

    conflicting_values: dict[str, dict[str, object]] = {
        "base@1.0.0": {"origin_layer": "base"},
        "web@1.0.0": {"origin_layer": "web"},
        "api@1.0.0": {"origin_layer": "api"},
        "full@1.0.0": {},
        "full2@1.0.0": {},
    }

    def extract_config(t: TemplateInfo) -> dict[str, object]:
        return conflicting_values[f"{t.name}@{t.meta.version}"]

    # full: web declared before api -> api (later-declared sibling) wins.
    resolution = Resolver().resolve("full@1.0.0", registry)
    assert resolution.execution_sequence == [
        "base@1.0.0",
        "web@1.0.0",
        "api@1.0.0",
        "full@1.0.0",
    ]
    assert resolution.execution_sequence.count("base@1.0.0") == 1

    composition = Composer(extract_config=extract_config).compose(resolution)
    assert [layer.name for layer in composition.layers] == [
        "base",
        "web",
        "api",
        "full",
    ]
    # Merged/winning value surfaces on `final`; layer order is the precedence
    # carrier underneath it (composition.layers[i] accumulates prior layers'
    # values, so the last layer to declare the key wins in `final` too).
    assert composition.final["origin_layer"] == "api"

    # full2: declaration flipped to [api, web] -> web (now later-declared) wins.
    resolution2 = Resolver().resolve("full2@1.0.0", registry)
    assert resolution2.execution_sequence == [
        "base@1.0.0",
        "api@1.0.0",
        "web@1.0.0",
        "full2@1.0.0",
    ]
    assert resolution2.execution_sequence.count("base@1.0.0") == 1

    composition2 = Composer(extract_config=extract_config).compose(resolution2)
    assert [layer.name for layer in composition2.layers] == [
        "base",
        "api",
        "web",
        "full2",
    ]
    assert composition2.final["origin_layer"] == "web"
