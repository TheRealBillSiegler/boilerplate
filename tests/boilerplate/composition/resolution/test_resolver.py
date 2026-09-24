from collections.abc import Callable

import pytest

from boilerplate.catalog import TemplateCatalog
from boilerplate.common.exceptions import InvalidTemplateSpecifierError
from boilerplate.composition import Resolver
from boilerplate.composition.graph import DependencyNotFoundError, VersionConflictError
from boilerplate.composition.resolution import Resolution
from boilerplate.models.template_info import TemplateInfo


def test_resolver_matches_function_behavior(
    template_factory: Callable[..., TemplateInfo],
) -> None:
    # Build a tiny in-memory catalog
    registry = TemplateCatalog()
    a = template_factory(
        "a", "1.0.0", extends=["b@1.0.0", "c"]
    )  # mixed pinned/unpinned
    b = template_factory("b", "1.0.0")
    c = template_factory("c", "2.0.0")
    c_old = template_factory("c", "1.0.0")

    # Register many (first one wins for same tag)
    registry.register_many([a, b, c, c_old])

    # Resolve via class
    res: Resolution = Resolver().resolve("a@1.0.0", registry)

    # Expected templates map includes all traversed nodes by specifier
    assert set(res.templates.keys()) == {"a@1.0.0", "b@1.0.0", "c@2.0.0"}

    # Expected dependency map preserves order declared in extends
    assert res.deps == {
        "a@1.0.0": ["b@1.0.0", "c@2.0.0"],
        "b@1.0.0": [],
        "c@2.0.0": [],
    }

    # Sanity: templates map points to the exact TemplateInfo objects we registered
    assert res.templates["a@1.0.0"] is a
    assert res.templates["b@1.0.0"] is b
    assert res.templates["c@2.0.0"] is c


def test_resolver_accepts_unversioned_root_and_picks_latest(
    template_factory: Callable[..., TemplateInfo],
) -> None:
    registry = TemplateCatalog()
    # Root available in two versions; unversioned should pick latest (1.0.0 over 0.9.0)
    a_090 = template_factory("a", "0.9.0", extends=["b"])  # unpinned dep
    a_100 = template_factory("a", "1.0.0", extends=["b"])  # latest root
    b_100 = template_factory("b", "1.0.0")
    b_200 = template_factory("b", "2.0.0")  # latest dependency
    registry.register_many([a_090, a_100, b_100, b_200])

    res: Resolution = Resolver().resolve("a", registry)

    # Root chosen is latest a@1.0.0; dependency b is latest b@2.0.0
    assert set(res.templates.keys()) == {"a@1.0.0", "b@2.0.0"}
    assert res.deps == {"a@1.0.0": ["b@2.0.0"], "b@2.0.0": []}


def test_resolver_raises_for_missing_dependency(
    template_factory: Callable[..., TemplateInfo],
) -> None:
    registry = TemplateCatalog()
    a = template_factory("a", "1.0.0", extends=["missing"])  # missing dep
    registry.register(a)

    with pytest.raises(DependencyNotFoundError):
        Resolver().resolve("a@1.0.0", registry)


def test_resolver_raises_invalid_specifier_for_malformed_extends(
    template_factory: Callable[..., TemplateInfo],
) -> None:
    registry = TemplateCatalog()
    a = template_factory("a", "1.0.0", extends=["b@not-a-version"])  # malformed
    registry.register(a)

    with pytest.raises(InvalidTemplateSpecifierError):
        Resolver().resolve("a@1.0.0", registry)


def test_resolver_handles_diamond_dependencies_once(
    template_factory: Callable[..., TemplateInfo],
) -> None:
    # c is shared by b1 and b2; ensure it's only processed once and present in the map
    registry = TemplateCatalog()
    c = template_factory("c", "1.0.0")
    b1 = template_factory("b1", "1.0.0", extends=["c@1.0.0"])  # pinned
    b2 = template_factory("b2", "1.0.0", extends=["c"])  # latest (still 1.0.0)
    a = template_factory(
        "a", "1.0.0", extends=["b1@1.0.0", "b2@1.0.0"]
    )  # order preserved
    registry.register_many([a, b1, b2, c])

    res: Resolution = Resolver().resolve("a@1.0.0", registry)

    assert set(res.templates.keys()) == {"a@1.0.0", "b1@1.0.0", "b2@1.0.0", "c@1.0.0"}
    assert res.deps["a@1.0.0"] == ["b1@1.0.0", "b2@1.0.0"]  # order preserved
    assert res.deps["b1@1.0.0"] == ["c@1.0.0"]
    assert res.deps["b2@1.0.0"] == ["c@1.0.0"]
    assert res.deps["c@1.0.0"] == []


def test_resolver_rejects_diamond_with_conflicting_versions(
    template_factory: Callable[..., TemplateInfo],
) -> None:
    # root extends [mid, base@1.0.0]; mid extends base (latest, 2.0.0) -> conflict
    registry = TemplateCatalog()
    base_v1 = template_factory("base", "1.0.0")
    base_v2 = template_factory("base", "2.0.0")
    mid = template_factory("mid", "1.0.0", extends=["base"])
    root = template_factory("root", "1.0.0", extends=["mid@1.0.0", "base@1.0.0"])
    registry.register_many([root, mid, base_v1, base_v2])

    with pytest.raises(VersionConflictError) as exc_info:
        Resolver().resolve("root@1.0.0", registry)

    assert exc_info.value.error_code == "BP_RESOLVE_VERSION_CONFLICT"
    message = str(exc_info.value)
    assert "base" in message
    assert "1.0.0" in message
    assert "2.0.0" in message


def test_resolver_deep_linear_chain(
    template_factory: Callable[..., TemplateInfo],
) -> None:
    registry = TemplateCatalog()
    # Build t0 -> t1 -> ... -> t9
    chain = [template_factory(f"t{i}", "1.0.0") for i in range(10)]
    # Set extends (except last)
    for i in range(9):
        chain[i].meta.extends = [f"t{i + 1}"]
    registry.register_many(chain)

    res: Resolution = Resolver().resolve("t0@1.0.0", registry)

    # All nodes present
    assert set(res.templates) == {f"t{i}@1.0.0" for i in range(10)}
    # Each node depends on the next, last has none
    for i in range(9):
        assert res.deps[f"t{i}@1.0.0"] == [f"t{i + 1}@1.0.0"]
    assert res.deps["t9@1.0.0"] == []


def test_resolver_wide_fanout_preserves_order(
    template_factory: Callable[..., TemplateInfo],
) -> None:
    registry = TemplateCatalog()
    a = template_factory("a", "1.0.0")
    children = [template_factory(f"b{i}", "1.0.0") for i in range(5)]
    a.meta.extends = [f"b{i}" for i in range(5)]  # unpinned, ordered
    registry.register_many([a, *children])

    res: Resolution = Resolver().resolve("a@1.0.0", registry)

    assert res.deps["a@1.0.0"] == [f"b{i}@1.0.0" for i in range(5)]
    for i in range(5):
        assert res.deps[f"b{i}@1.0.0"] == []


def test_resolver_cycle_smoke_no_hang_and_maps_include_cycle(
    template_factory: Callable[..., TemplateInfo],
) -> None:
    # Cycle detection is handled later by the graph layer; here we
    # ensure resolution completes
    registry = TemplateCatalog()
    a = template_factory("a", "1.0.0", extends=["b"])  # unpinned
    b = template_factory("b", "1.0.0", extends=["a@1.0.0"])  # pinned back to a
    registry.register_many([a, b])

    res: Resolution = Resolver().resolve("a@1.0.0", registry)

    assert set(res.templates) == {"a@1.0.0", "b@1.0.0"}
    # Each points to the other; visited guard prevents infinite recursion
    assert res.deps["a@1.0.0"] == ["b@1.0.0"]
    assert res.deps["b@1.0.0"] == ["a@1.0.0"]
