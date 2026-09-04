"""End-to-end resolution flow using real TemplateCatalog and Resolver."""

from collections.abc import Callable
from pathlib import Path

from boilerplate.catalog import TemplateCatalog
from boilerplate.composition import Resolver
from boilerplate.models.template_info import TemplateInfo


def test_resolve_builds_execution_sequence(
    tmp_path: Path, template_factory: Callable[..., TemplateInfo]
) -> None:
    # Build a tiny in-memory catalog with a diamond: full -> (web, api) -> base
    registry = TemplateCatalog()

    def mk(name: str, version: str, extends: list[str] | None = None) -> TemplateInfo:
        return template_factory(
            name, version, extends=extends or [], location=tmp_path / name
        )

    base = mk("base", "1.0.0")
    web = mk("web", "1.0.0", extends=["base@1.0.0"])
    api = mk("api", "1.0.0", extends=["base@1.0.0"])
    full = mk("full", "1.0.0", extends=["web@1.0.0", "api@1.0.0"])

    registry.register_many([base, web, api, full])

    resolution = Resolver().resolve("full@1.0.0", registry)
    execution_sequence = resolution.execution_sequence

    # base before web/api; web/api before full
    assert execution_sequence.index("base@1.0.0") < execution_sequence.index(
        "web@1.0.0"
    )
    assert execution_sequence.index("base@1.0.0") < execution_sequence.index(
        "api@1.0.0"
    )
    assert execution_sequence.index("web@1.0.0") < execution_sequence.index(
        "full@1.0.0"
    )
    assert execution_sequence.index("api@1.0.0") < execution_sequence.index(
        "full@1.0.0"
    )

    # Sanity on resolution structure
    assert "full@1.0.0" in resolution.templates
    assert resolution.templates["full@1.0.0"].name == "full"
    assert str(resolution.templates["full@1.0.0"].meta.version) == "1.0.0"
    assert resolution.templates["full@1.0.0"].location == tmp_path / "full"
